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

async def orchestrate_xml_downloads(limit: int = 50, outdir: str = "downloads/xml", headless: bool = False, ruc: str = None, periodo: str = None):
    """
    Busca comprobantes físicos pendientes en la base de datos, extrae la data preliminar
    requerida (monto, fecha) y orquesta la descarga usando el scraper de Playwright.
    """
    supabase = get_supabase()
    
    print(f"Buscando hasta {limit} comprobantes pendientes de descargar XML...")
    if ruc:
        print(f"  Filtro RUC: {ruc}")
    if periodo:
        print(f"  Filtro Periodo: {periodo}")
    
    # Resolve cliente_id from RUC first (more reliable than join filter)
    cliente_id = None
    if ruc:
        r = supabase.table("clientes").select("id").eq("ruc", ruc).execute()
        if not r.data:
            print(f"Error: No se encontró cliente con RUC {ruc}")
            return
        cliente_id = r.data[0]["id"]
    
    query = supabase.table("sire_comprobantes_fisicos") \
        .select(
            "id, cliente_id, periodo, tipo_libro, ruc_tercero, tipo_cp, serie, numero, reintentos, "
            "sire_preliminar_compras(fecha_emision, total_cp, car_sunat), "
            "sire_preliminar_ventas(fecha_emision, total_cp, car_sunat), "
            "clientes!inner(ruc, razon_social)"
        ) \
        .or_("estado_xml.in.(PENDIENTE,ERROR),estado_pdf.in.(PENDIENTE,ERROR)") \
        .lt("reintentos", 10)
        
    if cliente_id:
        query = query.eq("cliente_id", cliente_id)
    
    if periodo:
        query = query.eq("periodo", periodo)
        
    response = query.limit(limit).execute()
        
    records = response.data
    if not records:
        print("No hay comprobantes pendientes por descargar.")
        return
        
    print(f"Encontrados {len(records)} comprobantes en cola. Preparando queries...")
    
    queries: List[CpeQuery] = []
    record_map: Dict[str, dict] = {} # Map key to DB record ID
    
    for r in records:
        is_compra = (r["tipo_libro"] == "COMPRAS")
        preliminar = r["sire_preliminar_compras"] if is_compra else r["sire_preliminar_ventas"]
        
        if not preliminar:
            print(f"Registro {r['id']} no tiene data preliminar asociada. Saltando.")
            continue
            
        # Formatear fecha para el scraper (dd/mm/yyyy)
        fecha_db = preliminar.get("fecha_emision", "")
        fecha_scraper = ""
        if fecha_db:
            parts = fecha_db.split("-")
            if len(parts) == 3:
                fecha_scraper = f"{parts[2]}/{parts[1]}/{parts[0]}"
                
        # Get ruc_cliente
        ruc_cliente = r["clientes"]["ruc"] if r.get("clientes") else ""
        razon_social = r["clientes"]["razon_social"] if r.get("clientes") else ""
        
        q = CpeQuery(
            ruc_emisor=r["ruc_tercero"],
            tipo=r["tipo_cp"],
            serie=r["serie"],
            numero=r["numero"],
            importe=str(preliminar.get("total_cp", "")),
            fecha=fecha_scraper,
            period=r["periodo"],
            book="purchases" if is_compra else "sales",
            car_sunat=preliminar.get("car_sunat", ""),
            ruc_cliente=ruc_cliente,
            razon_social_cliente=razon_social
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
            prefer="either",
            headless=headless,
            skip_existing=False,
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
            if status in ("ok", "skipped"):
                paths = res.get("paths", [])
                # backwards compatibility with older returned dicts
                if "path" in res and res["path"]:
                    paths.append(res["path"])
                
                for ruta in paths:
                    ruta_lower = ruta.lower()
                    if ruta_lower.endswith(".pdf"):
                        update_data["estado_pdf"] = "DESCARGADO"
                        update_data["ruta_pdf"] = ruta
                    elif ruta_lower.endswith(".xml") or ruta_lower.endswith(".zip"):
                        update_data["estado_xml"] = "DESCARGADO"
                        update_data["ruta_xml"] = ruta
                    else:
                        update_data["estado_xml"] = "DESCARGADO"
                        update_data["ruta_xml"] = ruta

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
    parser.add_argument("--ruc", type=str, help="RUC de la empresa para filtrar")
    parser.add_argument("--periodo", type=str, help="Periodo a descargar (ej: 202604)")
    args = parser.parse_args()
    
    asyncio.run(orchestrate_xml_downloads(limit=args.limit, headless=args.headless, ruc=args.ruc, periodo=args.periodo))
