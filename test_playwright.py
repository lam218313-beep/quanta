from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        async with context.expect_event("page") as event_info:
            await page.evaluate("window.open('about:blank')")
        
        # Check if the event_info value is the page itself
        print(type(event_info.value).__name__)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
