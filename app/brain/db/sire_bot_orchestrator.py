import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure we can import app modules
root = Path(__file__).resolve().parents[3]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from app.brain.db.supabase_client import get_supabase
from app.brain.download_xml_scraper import CpeQuery, run_batch

async def orchestrate_xml_downloads(limit: int = 50, outdir: str = "downloads/xml", headless: bool = False):
    """
    Busca comprobantes físicos pendientes en la base de datos, extrae la data preliminar
    requerida (monto, fecha) y orquesta la descarga usando el scraper de Playwright.
    """
    supabase = get_supabase()
    
    print(f"Buscando hasta {limit} comprobantes pendientes de descargar XML...")
    
    # Query Supabase: get fisicos joining with compras and ventas
    # Since foreign keys exist, Supabase API allows nested selects.
    response = supabase.table("sire_comprobantes_fisicos") \
        .select(
            "id, cliente_id, periodo, tipo_libro, ruc_tercero, tipo_cp, serie, numero, reintentos, "
            "sire_preliminar_compras(fecha_emision, total_cp, car_sunat), "
            "sire_preliminar_ventas(fecha_emision, total_cp, car_sunat)"
        ) \
        .eq("estado_xml", "PENDIENTE") \
        .lt("reintentos", 3) \
        .limit(limit) \
        .execute()
        
    records = response.data
    if not records:
        print("✅ No hay comprobantes pendientes por descargar.")
        return
        
    print(f"Encontrados {len(records)} comprobantes en cola. Preparando queries...")
    
    queries: List[CpeQuery] = []
    record_map: Dict[str, dict] = {} # Map key to DB record ID
    
    for r in records:
        is_compra = (r["tipo_libro"] == "COMPRAS")
        preliminar = r["sire_preliminar_compras"] if is_compra else r["sire_preliminar_ventas"]
        
        if not preliminar:
            print(f"⚠️ Registro {r['id']} no tiene data preliminar asociada. Saltando.")
            continue
            
        # Formatear fecha para el scraper (dd/mm/yyyy)
        fecha_db = preliminar.get("fecha_emision", "")
        fecha_scraper = ""
        if fecha_db:
            parts = fecha_db.split("-")
            if len(parts) == 3:
                fecha_scraper = f"{parts[2]}/{parts[1]}/{parts[0]}"
                
        # Scraper needs: ruc_emisor, tipo, serie, numero, importe, fecha
        # In compras, the third party is the emisor. In ventas, we are the emisor, but wait, 
        # for SUNAT query, if we emit, the form handles it via the "Emitidos" tab.
        # But wait, download_xml_scraper defaults to "Recibidos" or looks for rucEmisor.
        # Actually download_xml_scraper always searches using the third-party RUC in the form.
        
        q = CpeQuery(
            ruc_emisor=r["ruc_tercero"],
            tipo=r["tipo_cp"],
            serie=r["serie"],
            numero=r["numero"],
            importe=str(preliminar.get("total_cp", "")),
            fecha=fecha_scraper,
            period=r["periodo"],
            book="purchases" if is_compra else "sales",
            car_sunat=preliminar.get("car_sunat", "")
        )
        queries.append(q)
        
        key = f"{q.period}-{q.ruc_emisor}-{q.tipo}-{q.serie}-{q.numero}"
        record_map[key] = r
        
        # Increment intentos
        supabase.table("sire_comprobantes_fisicos") \
            .update({"reintentos": r["reintentos"] + 1}) \
            .eq("id", r["id"]) \
            .execute()
            
    if not queries:
        return
        
    print("Iniciando Playwright scraper...")
    try:
        results = await run_batch(
            queries,
            outdir=str(Path(root) / outdir),
            prefer="xml",
            headless=headless,
            skip_existing=True,
            limit=limit
        )
        
        print("\nProcesando resultados y actualizando la base de datos...")
        for res in results:
            key = f"{res['period']}-{res['ruc_emisor']}-{res['tipo']}-{res['serie']}-{res['numero']}"
            db_record = record_map.get(key)
            if not db_record:
                continue
                
            status = res.get("status")
            ruta = res.get("path", "")
            
            update_data = {}
            if status == "ok":
                update_data["estado_xml"] = "DESCARGADO"
                update_data["ruta_xml"] = ruta
            elif status == "skipped":
                update_data["estado_xml"] = "DESCARGADO"
                # Find the existing file path
                base_name = f"{res['ruc_emisor']}-{res['tipo']}-{res['serie']}-{res['numero']}"
                out_path = Path(root) / outdir / res['period'] / res['book'] / base_name
                for ext in (".zip", ".xml", ".XML"):
                    if out_path.with_suffix(ext).exists():
                        update_data["ruta_xml"] = str(out_path.with_suffix(ext))
                        break
            elif status == "not_found":
                update_data["estado_xml"] = "NO_EXISTE"
            else:
                update_data["estado_xml"] = "ERROR"
                update_data["error_log"] = res.get("error", "Error desconocido")
                
            supabase.table("sire_comprobantes_fisicos") \
                .update(update_data) \
                .eq("id", db_record["id"]) \
                .execute()
                
        print("Base de datos de comprobantes físicos actualizada.")
        
    except Exception as e:
        print(f"Error catastrófico en la orquestación: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    
    asyncio.run(orchestrate_xml_downloads(limit=args.limit, headless=args.headless))
