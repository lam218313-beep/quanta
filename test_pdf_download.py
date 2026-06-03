import asyncio
from pathlib import Path
from app.brain.download_xml_scraper import run_batch, CpeQuery

async def main():
    queries = [
        CpeQuery(
            ruc_emisor="20615048349", # Some invoice from Ecoservis
            tipo="01",
            serie="E001",
            numero="170",
            fecha="01/04/2026",
            importe="100.00",
            ruc_cliente="20614169754",
            razon_social_cliente="ECOSERVIS",
            period="202604",
            book="sales"
        )
    ]
    
    outdir = Path("downloads/xml")
    
    print("Iniciando prueba de descarga...")
    results = await run_batch(
        queries,
        outdir=str(outdir),
        prefer="pdf",
        headless=True,
        skip_existing=False,
        limit=1
    )
    
    for r in results:
        print(r)

if __name__ == "__main__":
    asyncio.run(main())
