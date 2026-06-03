import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto('https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm')
        await asyncio.sleep(5)
        html = await page.content()
        print('Has RUC:', 'txtRuc' in html)
        await browser.close()

asyncio.run(test())