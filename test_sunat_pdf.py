import asyncio
from pathlib import Path
from app.brain.download_xml_scraper import _load_sunat_session_cookies
from playwright.async_api import async_playwright

async def main():
    ruc_cliente = "20614169754"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            accept_downloads=True,
        )
        page = await context.new_page()
        
        # Load state
        cookies = _load_sunat_session_cookies(ruc_cliente)
        await context.add_cookies(cookies)
            
        # Navigate to portal
        await page.goto("https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm")
        await page.wait_for_selector("#divModalCampana", timeout=5000)
        await page.evaluate("document.querySelector('#divModalCampana')?.remove()")
        await page.evaluate("document.querySelector('#divModalCampanaBak')?.remove()")
        
        await page.goto("https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm?action=execute&actionName=astranCmpcpeConsultaOpciones&estado=act&origen=retCpe&url=https://e-factura.sunat.gob.pe/cl-ti-itconscomprobante/consultaComprobante.htm")
        
        await page.wait_for_selector("consulta-comprobante-individual")
        
        # Fill form for 20615048349-01-E001-170
        frame = page.locator("consulta-comprobante-individual")
        await frame.locator("input[formcontrolname='rucEmisor']").fill("20615048349")
        await frame.locator("input[formcontrolname='serieComprobante']").fill("E001")
        await frame.locator("input[formcontrolname='numeroComprobante']").fill("170")
        
        await frame.locator("button:has-text('Consultar')").click()
        
        await page.wait_for_selector("button:has-text('PDF')", timeout=10000)
        
        print("Found PDF button. Waiting for events...")
        target = page.locator("button:has-text('PDF')").first
        
        # We will wait for either page or download
        dl_task = asyncio.create_task(context.wait_for_event("download", timeout=15000))
        page_task = asyncio.create_task(context.wait_for_event("page", timeout=15000))
        
        await target.click()
        
        done, pending = await asyncio.wait([dl_task, page_task], return_when=asyncio.FIRST_COMPLETED)
        
        for t in done:
            try:
                res = t.result()
                print(f"Event triggered: {type(res)}")
                if "Download" in str(type(res)):
                    print(f"Download URL: {res.url}")
                    print(f"Suggested name: {res.suggested_filename}")
                else:
                    print(f"Page URL: {res.url}")
            except Exception as e:
                print(f"Task failed: {e}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
