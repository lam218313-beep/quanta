import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            accept_downloads=True,
        )
        page = await context.new_page()
        
        print("Logging in...")
        await page.goto("https://api-seguridad.sunat.gob.pe/v1/clientessol/4f25a00c-4eec-41ed-abf7-b4c986d42152/oauth2/loginMenuSol?originalUrl=https://e-menu.sunat.gob.pe/cl-ti-itmenu/AutenticaMenuInternet.htm&state=rO0ABXNyABFqYXZhLnV0aWwuSGFzaE1hcAUH2sHDFmDRAwACRgAKbG9hZEZhY3RvckkACXRocmVzaG9sZHhwP0AAAAAAAAx3CAAAABAAAAADdAAQZXN0YWRvQ29udHJpYnV5dAAIQUNUSVZPUyB0AAZ1YmlnZW90AAQxNTAxdAAOZXN0YWRvRG9taWNpbGlvdAABSHg=")
        await page.wait_for_selector("#txtRuc")
        await page.fill("#txtRuc", "20614169754")
        await page.fill("#txtUsuario", "18222009")
        await page.fill("#txtContrasena", "Moises2025")
        await page.click("#btnAceptar")
        
        await page.wait_for_selector("#divModalCampana", timeout=10000)
        await page.evaluate("document.querySelector('#divModalCampana')?.remove()")
        await page.evaluate("document.querySelector('#divModalCampanaBak')?.remove()")
        
        print("Navigating to Consulta...")
        await page.goto("https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm?action=execute&actionName=astranCmpcpeConsultaOpciones&estado=act&origen=retCpe&url=https://e-factura.sunat.gob.pe/cl-ti-itconscomprobante/consultaComprobante.htm")
        
        await page.wait_for_selector("consulta-comprobante-individual")
        
        frame = page.locator("consulta-comprobante-individual")
        await frame.locator("input[formcontrolname='rucEmisor']").fill("20615048349")
        await frame.locator("input[formcontrolname='serieComprobante']").fill("E001")
        await frame.locator("input[formcontrolname='numeroComprobante']").fill("170")
        
        print("Consulting...")
        await frame.locator("button:has-text('Consultar')").click()
        
        await page.wait_for_selector("button:has-text('PDF')", timeout=10000)
        
        print("Found PDF button. Waiting for events...")
        target = page.locator("button:has-text('PDF')").first
        
        dl_task = asyncio.create_task(context.wait_for_event("download", timeout=10000))
        page_task = asyncio.create_task(context.wait_for_event("page", timeout=10000))
        
        await target.click()
        print("Clicked PDF button.")
        
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
