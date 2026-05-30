import asyncio
from playwright.async_api import async_playwright
import os
import json
from dotenv import load_dotenv

# Load Env
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

SUNAT_LOGIN_URL = "https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm"

async def run():
    async with async_playwright() as p:
        # Launch browser in HEADED mode so user can see and interact
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("🚀 Opening SUNAT Login Page...")
        print("👤 Please Log In manually in the browser window.")
        
        await page.goto(SUNAT_LOGIN_URL)

        print("⏳ Waiting for user to log in...")
        print("👉 IMPORTANT: Once inside the menu, please click on:")
        print("   'Empresas' -> 'Comprobantes de Pago' -> 'Consulta de Comprobantes de Pago' -> 'Nueva Consulta de comprobantes de pago'")
        print("   (This step is required to generate the specific cookies we need for XML downloads)")
        
        # Smart Session Detection: Poll for cookies
        max_retries = 100 # 5 minutes
        found_session = False
        
        try:
            for i in range(max_retries):
                cookies = await context.cookies()
                
                # Check for known authenticated session cookies
                itcons_cookie = next((c for c in cookies if "ITCONS" in c['name'] or "cFallo" in c['name']), None)
                ts_cookie = next((c for c in cookies if c['name'].startswith("TS")), None)
                
                # Strict Success: Found the Legacy Cookie
                if itcons_cookie:
                    print(f"✅ Login detected! Found LEGACY cookie: {itcons_cookie['name']}")
                    found_session = True
                    break
                
                # Fallback Success: Found enough TS cookies (user might be in menu but not legacy app)
                # We will accept this but warn the user
                ts_cookies = [c for c in cookies if c['name'].startswith("TS")]
                if len(ts_cookies) >= 2 and i > 10:
                     print(f"⚠️ Ambiguous Login: Found {len(ts_cookies)} TS cookies but no ITCONS.")
                     print("   Proceeding... (Hope this works!)")
                     found_session = True
                     break
                
                if i % 5 == 0:
                    print(f"   ... waiting. Please open 'Consulta Validez' inside the menu. (Attempt {i}/{max_retries})")
                
                await asyncio.sleep(3)
            
            # Extract Cookies Final
            cookies = await context.cookies()
            
            if found_session:
                print(f"🎉 Success! Extracted {len(cookies)} cookies.")
                print("   (Wait 5s to ensure full loading...)")
                await asyncio.sleep(5)
                
                # Save cookies to a file
                cookie_file = os.path.join(os.path.dirname(__file__), "sunat_session.json")
                with open(cookie_file, "w") as f:
                    json.dump(cookies, f, indent=2)
                
                print(f"💾 Session saved to: {cookie_file}")
            else:
                print("❌ Timeout: Did not detect session cookies after 5 minutes.")
        except Exception as e:
            print(f"❌ Error during scrape: {e}")
        
        print("👋 Closing browser in 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
