import os
import sys
from pathlib import Path

# Ensure we can import app modules
root = Path(__file__).resolve().parents[3]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from app.brain.db.supabase_client import get_supabase
from app.brain.sire_xml_matcher import _extract_from_xml

def enrich_preliminary_data(limit: int = 500):
    """
    Busca comprobantes físicos que ya tienen su XML descargado (estado_xml = 'DESCARGADO')
    pero que aún no han enriquecido la tabla preliminar. Extrae la glosa y detracción del XML
    y hace un UPDATE en sire_preliminar_compras o sire_preliminar_ventas.
    """
    supabase = get_supabase()
    
    print(f"Buscando XMLs descargados para enriquecer (límite {limit})...")
    
    response = supabase.table("sire_comprobantes_fisicos") \
        .select(
            "id, tipo_libro, ruta_xml, preliminar_compra_id, preliminar_venta_id, "
            "sire_preliminar_compras(estado_enriquecimiento), "
            "sire_preliminar_ventas(estado_enriquecimiento)"
        ) \
        .eq("estado_xml", "DESCARGADO") \
        .not_.is_("ruta_xml", "null") \
        .limit(limit) \
        .execute()
        
    records = response.data
    if not records:
        print("No hay XMLs pendientes por enriquecer.")
        return
        
    to_enrich = []
    
    # Filter those that actually need enrichment
    for r in records:
        is_compra = (r["tipo_libro"] == "COMPRAS")
        preliminar = r["sire_preliminar_compras"] if is_compra else r["sire_preliminar_ventas"]
        
        if not preliminar:
            continue
            
        if preliminar.get("estado_enriquecimiento") != "COMPLETO":
            to_enrich.append(r)
            
    if not to_enrich:
        print("Todos los XMLs descargados ya fueron enriquecidos.")
        return
        
    print(f"Encontrados {len(to_enrich)} comprobantes listos para extraer data.")
    
    for r in to_enrich:
        ruta_xml = r.get("ruta_xml")
        xml_path = Path(ruta_xml)
        
        is_compra = (r["tipo_libro"] == "COMPRAS")
        preliminar_id = r["preliminar_compra_id"] if is_compra else r["preliminar_venta_id"]
        table_name = "sire_preliminar_compras" if is_compra else "sire_preliminar_ventas"
        
        if not xml_path.exists():
            print(f"Advertencia: Archivo XML no encontrado en disco: {ruta_xml}")
            # Mark as ERROR in enrichment so we don't infinitely retry unless reset
            supabase.table(table_name) \
                .update({"estado_enriquecimiento": "ERROR"}) \
                .eq("id", preliminar_id) \
                .execute()
            continue
            
        try:
            info = _extract_from_xml(xml_path)
            
            if info:
                desc_text = "; ".join(info.get("descriptions", []))
                detraccion = info.get("detraccion", "NO")
                
                # Update preliminary table
                supabase.table(table_name) \
                    .update({
                        "descripcion_comprobante": desc_text if desc_text else "Sin descripción",
                        "estado_enriquecimiento": "COMPLETO",
                        # We could also update the detraccion column if we want to overwrite SIRE's
                    }) \
                    .eq("id", preliminar_id) \
                    .execute()
                    
                print(f"Enriquecido {xml_path.name}: {desc_text[:50]}...")
            else:
                print(f"Advertencia: No se pudo extraer info de {xml_path.name}")
                supabase.table(table_name) \
                    .update({"estado_enriquecimiento": "ERROR"}) \
                    .eq("id", preliminar_id) \
                    .execute()
                    
        except Exception as e:
            print(f"Error al procesar {ruta_xml}: {e}")
            
    print("Proceso de enriquecimiento finalizado.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    
    enrich_preliminary_data(limit=args.limit)
