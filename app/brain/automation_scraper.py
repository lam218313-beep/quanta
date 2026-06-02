import asyncio
from playwright.async_api import async_playwright
import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

def _ensure_import_path() -> None:
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)

# Load Env
load_dotenv(_repo_root() / '.env')

SUNAT_LOGIN_URL = "https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm"

import argparse

async def run(ruc: str):
    async with async_playwright() as p:
        # Launch browser in HEADED mode so user can see and interact
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"🚀 Opening SUNAT Login Page for RUC {ruc}...")
        await page.goto(SUNAT_LOGIN_URL)
        await asyncio.sleep(2)
        
        # Intentar autocompletado si hay credenciales
        _ensure_import_path()
        from app.brain.db.supabase_client import get_supabase
        supabase = get_supabase()
        resp = supabase.table("clientes").select("usuario_sol, clave_sol").eq("ruc", ruc).execute()
        
        if resp.data and resp.data[0].get("usuario_sol") and resp.data[0].get("clave_sol"):
            print("🔑 Credentials found in database! Auto-filling form...")
            try:
                usuario = resp.data[0]["usuario_sol"]
                clave = resp.data[0]["clave_sol"]
                
                await page.fill("#txtRuc", ruc)
                await page.fill("#txtUsuario", usuario)
                await page.fill("#txtContrasena", clave)
                await page.click("#btnAceptar")
                print("   Login button clicked. Waiting for response...")
            except Exception as e:
                print(f"   Auto-fill failed: {e}. Please log in manually.")
        else:
            print("👤 No credentials found. Please Log In manually in the browser window.")

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
                
                # Save cookies to a file based on RUC
                cookie_file = os.path.join(os.path.dirname(__file__), f"sunat_session_{ruc}.json")
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
    parser = argparse.ArgumentParser(description="SUNAT Manual Login")
    parser.add_argument("--ruc", required=True, help="RUC of the client you are logging into")
    args = parser.parse_args()
    
    asyncio.run(run(args.ruc))
