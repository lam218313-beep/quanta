"""SUNAT XML/PDF Scraper – Downloads CPEs from 'Consulta de Comprobantes de Pago'.

This scraper navigates the SUNAT SOL portal to the section where comprobantes
(received or emitted) can be listed and downloaded as XML or PDF.

Menu path:  Comprobantes de pago → Comprobantes de Pago → Consulta de
            Comprobantes de Pago → Nueva Consulta de comprobantes de pago
Code:       11.38.1.1.1

Usage:
  1) Run automation_scraper.py to login manually and save cookies.
  2) Use run_batch() from sire_xml_scrape_cli.py for batch downloads.
"""

import asyncio
import json
import os
import sys
from playwright.async_api import async_playwright
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Literal, Optional

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MENU_URL = "https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm"

# Menu code for "Nueva Consulta de comprobantes de pago"
CONSULTA_CPE_CODE = "11.38.1.1.1"

DownloadPrefer = Literal["xml", "pdf", "either"]


@dataclass(frozen=True)
class CpeQuery:
    """A single CPE to look up / download."""
    ruc_emisor: str
    tipo: str       # "01"=Factura, "03"=Boleta, "07"=NC, "08"=ND
    serie: str
    numero: str
    importe: str    # Total amount (for validation)
    fecha: str      # dd/mm/yyyy
    period: str = ""    # YYYYMM for output organization
    book: str = ""      # purchases | sales
    car_sunat: str = ""


# ---------------------------------------------------------------------------
# Cookie / session helpers
# ---------------------------------------------------------------------------

def _load_sunat_session_cookies() -> list[dict]:
    cookie_file = os.path.join(os.path.dirname(__file__), "sunat_session.json")
    if not os.path.exists(cookie_file):
        raise FileNotFoundError(
            "Session file not found. Run automation_scraper.py first to create brain/sunat_session.json"
        )
    with open(cookie_file, "r") as f:
        return json.load(f)


def _default_user_agent() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------

async def _dismiss_overlays(page):
    """Remove known campaign/modal overlays that block clicks."""
    for sel in ("#divModalCampana", "#divModalCampanaBak"):
        try:
            if await page.locator(sel).is_visible(timeout=500):
                print(f"   ⚠️ Overlay detected: {sel}. Removing…")
                await page.evaluate(
                    f"document.querySelector('{sel}') && document.querySelector('{sel}').remove()"
                )
                await asyncio.sleep(0.3)
        except Exception:
            pass


async def _navigate_to_consulta_cpe(page):
    """Navigate from the SUNAT SOL main menu to the CPE query form.

    Uses the JavaScript function ``ejecuta()`` with menu code 11.38.1.1.1
    to open "Nueva Consulta de comprobantes de pago" inside #iframeApplication.
    """
    print("⏳ Navigating to Consulta de Comprobantes de Pago…")
    await page.wait_for_load_state("networkidle")
    await _dismiss_overlays(page)

    old_pages = list(page.context.pages)
    # Click the menu item natively using jQuery (to trigger their exact internal routing)
    try:
        await page.evaluate("$('#nivel4_11_38_1_1_1').click()")
    except Exception as e:
        print(f"   ⚠️ JS click() raised: {e}")

    await asyncio.sleep(4)

    # Check if a new page/tab opened
    new_pages = list(page.context.pages)
    if len(new_pages) > len(old_pages):
        page = new_pages[-1]

    await page.wait_for_load_state()

    # Resolve the iframe that hosts the application
    iframe_sel = "#iframeApplication"
    try:
        await page.wait_for_selector(iframe_sel, state="attached", timeout=15000)
    except Exception:
        # Fallback: sometimes there's an intermediate frame
        pass

    eh = await page.query_selector(iframe_sel)
    frame = await eh.content_frame() if eh else None
    if not frame:
        raise RuntimeError("Could not resolve #iframeApplication frame")

    # Wait for the form to appear (the consulta page should have a date filter or a table)
    # The form may have different layouts, let's wait for something generic
    try:
        await frame.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    await asyncio.sleep(2)
    return page, frame


async def _setup_filters_and_search(frame, *, ruc: str, fecha_desde: str, fecha_hasta: str):
    """Fill the search form inside the CPE query page and click 'Buscar'.

    Parameters
    ----------
    frame : Playwright Frame inside #iframeApplication
    ruc : The RUC to search (emisor or receptor depending on context)
    fecha_desde, fecha_hasta : dd/mm/yyyy date range
    """
    print(f"   📅 Filtering: {fecha_desde} – {fecha_hasta} | RUC: {ruc}")

    # The "Nueva Consulta" page has various filter fields.
    # Try to fill them, but some might not exist depending on the SUNAT version.

    # Type of search: Recibidos (received) or Emitidos (sent)
    # Try to click the "Recibidos" tab/radio if available
    for sel in [
        "input[value='recibidos']",
        "label:has-text('Recibidos')",
        "#rbRecibidos",
        "input[name='tipoConsulta'][value='2']",
    ]:
        try:
            if await frame.locator(sel).count() > 0:
                await frame.locator(sel).first.click()
                await asyncio.sleep(0.5)
                break
        except Exception:
            continue

    # Date range
    for sel in ["#fechaDesde", "input[name='fechaDesde']", "#fecDesde", "input[name='fecDesde']"]:
        try:
            if await frame.locator(sel).count() > 0:
                await frame.locator(sel).first.fill(fecha_desde)
                break
        except Exception:
            continue

    for sel in ["#fechaHasta", "input[name='fechaHasta']", "#fecHasta", "input[name='fecHasta']"]:
        try:
            if await frame.locator(sel).count() > 0:
                await frame.locator(sel).first.fill(fecha_hasta)
                break
        except Exception:
            continue

    await asyncio.sleep(0.5)

    # Click Buscar / Consultar
    for sel in [
        "button#btnBuscar",
        "button:has-text('Buscar')",
        "button:has-text('Consultar')",
        "#btnConsultar",
        "input[type='submit']",
        "button.btn-primary",
    ]:
        try:
            if await frame.locator(sel).count() > 0:
                await frame.locator(sel).first.click(timeout=8000)
                break
        except Exception:
            continue

    await asyncio.sleep(3)
    try:
        await frame.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core: search-and-download for a single CPE via the individual query form
# ---------------------------------------------------------------------------

async def _search_individual(
    *,
    page,
    frame,
    query: CpeQuery,
    out_path: Path,
    prefer: DownloadPrefer,
    debug_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Fill the individual CPE search form, check results, and download.

    This function handles the 'Consulta Individual' tab inside the
    Consulta de Comprobantes page.
    """
    base_name = f"{query.ruc_emisor}-{query.tipo}-{query.serie}-{query.numero}"
    print(f"📝 Query: {base_name}")

    # Check if we are in the new Angular form by looking for 'rucEmisor' formcontrolname
    is_angular = await frame.locator("input[formcontrolname='rucEmisor']").count() > 0

    if is_angular:
        # 1. Select Recibido (assuming we are searching for purchases/supplier invoices)
        # In a generic way, if we need to type a different RUC, we MUST click Recibido
        try:
            await frame.locator("#recibido").check(force=True)
            await asyncio.sleep(0.5)
        except Exception:
            pass

        # 2. Fill RUC
        try:
            await frame.locator("input[formcontrolname='rucEmisor']").fill(query.ruc_emisor)
        except Exception as e:
            print(f"   ⚠️ Could not fill rucEmisor: {e}")

        # 3. Tipo Comprobante (PrimeNG dropdown)
        try:
            dropdown = frame.locator("p-dropdown[formcontrolname='tipoComprobanteI']")
            await dropdown.click()
            await asyncio.sleep(0.5)
            
            tipo_map = {
                "01": "Factura",
                "03": "Boleta",
                "07": "Crédito",
                "08": "Débito"
            }
            label = tipo_map.get(query.tipo, "Factura")
            
            # Look for the dropdown item containing the code e.g. "01 - " or the label
            item_loc = frame.locator(f"p-dropdownitem li:has-text('{query.tipo} - ')")
            if await item_loc.count() == 0:
                item_loc = frame.locator(f"p-dropdownitem li:has-text('{label}')")
                
            if await item_loc.count() > 0:
                await item_loc.first.click()
            else:
                print(f"   ⚠️ Could not find dropdown option for {query.tipo}")
                # Click outside to close dropdown
                await frame.evaluate("document.body.click()")
        except Exception as e:
            print(f"   ⚠️ Could not select tipoComprobante: {e}")

        # 4. Serie & Numero
        try:
            await frame.locator("input[formcontrolname='serieComprobante']").fill(query.serie)
            await frame.locator("input[formcontrolname='numeroComprobante']").fill(query.numero)
        except Exception as e:
            print(f"   ⚠️ Could not fill serie/numero: {e}")
            
    else:
        # Legacy form filling
        field_map = {
            "numRuc": query.ruc_emisor,
            "codComp": query.tipo,
            "numeroSerie": query.serie,
            "numero": query.numero,
            "fechaEmision": query.fecha,
            "monto": query.importe,
        }

        for name, value in field_map.items():
            try:
                loc = frame.locator(f"[name='{name}']")
                if await loc.count() > 0:
                    tag = await loc.first.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        await loc.first.select_option(value=value)
                    else:
                        await loc.first.fill(value)
                    await asyncio.sleep(0.2)
            except Exception as e:
                print(f"   ⚠️ Could not fill {name}: {e}")

    # Click the Consultar button
    for sel in [
        "#btnConsultar",
        "button:has-text('Consultar')",
        "button:has-text('Buscar')",
        "#btnAceptar",
        "button.btn-primary",
    ]:
        try:
            if await frame.locator(sel).count() > 0:
                await frame.locator(sel).first.click(timeout=8000)
                break
        except Exception:
            continue

    await asyncio.sleep(3)

    # Check if we got a result
    try:
        body_text = await frame.evaluate("document.body.innerText")
    except Exception:
        body_text = ""

    # The result panel varies heavily between Angular and legacy apps.
    # Assume found unless we see explicit "no results" text
    found = True
    
    not_found_texts = [
        "No se encontraron registros",
        "0 de un total de 0",
        "No existen datos para los criterios",
        "El comprobante no existe",
        "No existe información",
    ]
    if any(t.lower() in body_text.lower() for t in not_found_texts):
        found = False

    if not found:
        # Save debug artifacts
        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                await page.screenshot(path=str(debug_dir / f"not_found-{base_name}.png"))
                html = await frame.content()
                (debug_dir / f"not_found-{base_name}.html").write_text(html, encoding="utf-8")
            except Exception:
                pass
        return None

    print(f"   ✅ Found: {base_name}")
    
    # Dump result modal HTML for debugging
    if debug_dir:
        try:
            debug_dir.mkdir(parents=True, exist_ok=True)
            html = await frame.content()
            (debug_dir / f"_debug_result_modal.html").write_text(html, encoding="utf-8")
        except Exception:
            pass

    # Try to find XML/PDF download button
    xml_sels = [
        "a:has-text('XML')", "button:has-text('XML')",
        "[title*='XML']", "[onclick*='xml']", "[onclick*='XML']",
        "button[ngbtooltip*='XML']", "button[ngbtooltip*='xml']",
        "button:has(i.fa-file-code)", "button:has(i.fa-file-excel)",
        ".button-container button:nth-of-type(2)", # Angular modal (2nd button)
    ]
    pdf_sels = [
        "a:has-text('PDF')", "button:has-text('PDF')",
        "[title*='PDF']", "[onclick*='pdf']", "[onclick*='PDF']",
        "button[ngbtooltip*='PDF']", "button[ngbtooltip*='pdf']",
        "button:has(i.fa-file-pdf)",
        ".button-container button:nth-of-type(1)", # Angular modal (1st button)
    ]
    fallback_sels = [
        "a:has-text('Descargar')", "button:has-text('Descargar')",
        "button[ngbtooltip*='Descargar']",
        "a:has-text('Imprimir')", "button[ngbtooltip*='Imprimir']"
    ]

    targets = []
    
    # Check XML selectors
    for sel in xml_sels:
        try:
            if await frame.locator(sel).count() > 0:
                targets.append(("xml", frame.locator(sel).first))
                break
        except Exception:
            continue
            
    # Check PDF selectors
    for sel in pdf_sels:
        try:
            if await frame.locator(sel).count() > 0:
                targets.append(("pdf", frame.locator(sel).first))
                break
        except Exception:
            continue
            
    # Fallback if neither found
    if not targets:
        for sel in fallback_sels:
            try:
                if await frame.locator(sel).count() > 0:
                    targets.append(("fallback", frame.locator(sel).first))
                    break
            except Exception:
                continue

    if not targets:
        print(f"   ⚠️ Comprobante found but NO download button available")
        # Save the result as a "validation only" record
        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                await page.screenshot(path=str(debug_dir / f"no_download-{base_name}.png"))
                html = await frame.content()
                (debug_dir / f"no_download-{base_name}.html").write_text(html, encoding="utf-8")
            except Exception:
                pass
                
        # Close modal for next query
        try:
            close_btns = frame.locator("button.close, button.close-without-header, button[aria-label='Close']")
            count = await close_btns.count()
            for i in range(count - 1, -1, -1):
                await close_btns.nth(i).click(force=True, timeout=1000)
                await asyncio.sleep(0.3)
        except Exception:
            pass
        return None

    # Download the files
    out_path.parent.mkdir(parents=True, exist_ok=True)
    downloaded_paths = []
    
    for file_type, target in targets:
        try:
            async with page.expect_download(timeout=45000) as dl_info:
                await target.click()
                
                # Check for the warning modal "El archivo se ha descargado previamente"
                try:
                    accept_btn = frame.locator("button:has-text('Aceptar'), .swal2-confirm")
                    if await accept_btn.count() > 0:
                        await accept_btn.first.click(timeout=2000)
                except Exception:
                    pass
                    
            download = await dl_info.value
            suggested = download.suggested_filename or "download"
            ext = os.path.splitext(suggested)[1] or f".{file_type}"
            
            # Use specific extension if possible to avoid overwriting
            if ext.lower() == ".bin" and file_type != "fallback":
                ext = f".{file_type}"
                
            final_path = out_path.with_suffix(ext)
            await download.save_as(str(final_path))
            downloaded_paths.append(final_path)
            
            # Short delay between downloads
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Download failed for {file_type}: {e}")
            
    # Close modal for next query
    try:
        close_btns = frame.locator("button.close, button.close-without-header, button[aria-label='Close']")
        count = await close_btns.count()
        for i in range(count - 1, -1, -1):
            await close_btns.nth(i).click(force=True, timeout=1000)
            await asyncio.sleep(0.3)
    except Exception:
        pass
        
    if not downloaded_paths:
        return None
        
    # Return the first path to keep backwards compatibility, or maybe return all if needed.
    # The CLI currently expects a single Path or string, but returning the primary one is fine.
    # Actually, returning the downloaded_paths list might break the caller, let's just return the XML one if possible, or the first one.
    xml_paths = [p for p in downloaded_paths if str(p).endswith(".xml")]
    if xml_paths:
        return xml_paths[0]
    return downloaded_paths[0]


async def _clear_form(frame, page=None):
    """Click 'Limpiar' to reset the form for the next query and ensure modals are closed."""
    # Force close any open modals using Playwright explicit clicks
    try:
        close_btns = frame.locator("button.close, button.close-without-header, button[aria-label='Close']")
        count = await close_btns.count()
        for i in range(count - 1, -1, -1):
            await close_btns.nth(i).click(force=True, timeout=1000)
            await asyncio.sleep(0.3)
    except Exception:
        pass

    for sel in [
        "#btnLimpiar",
        "button:has-text('Limpiar')",
        "button.p-button-outlined", # Common PrimeNG secondary button class
    ]:
        try:
            if await frame.locator(sel).count() > 0:
                await frame.locator(sel).first.click(timeout=3000)
                await asyncio.sleep(1)
                return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

async def run_batch(
    queries: Iterable[CpeQuery],
    *,
    outdir: str,
    prefer: DownloadPrefer = "xml",
    headless: bool = False,
    skip_existing: bool = True,
    limit: int = 0,
) -> list[dict]:
    """Open browser, navigate to Consulta de Comprobantes, and download each CPE.

    Returns a list of result dicts with keys:
      status, ruc_emisor, tipo, serie, numero, period, book, path, error
    """
    cookies = _load_sunat_session_cookies()
    out_base = Path(outdir).expanduser().resolve()
    results: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=_default_user_agent(),
            accept_downloads=True,
        )
        await context.add_cookies(cookies)

        page = await context.new_page()
        print("🚀 Navigating to SUNAT Main Menu…")
        await page.goto(MENU_URL)
        await _dismiss_overlays(page)

        # Navigate to the Consulta de Comprobantes form
        page, frame = await _navigate_to_consulta_cpe(page)

        # Dump the frame HTML for debug (first time only)
        try:
            debug_html = await frame.content()
            debug_path = out_base / "_debug_consulta_form.html"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(debug_html, encoding="utf-8")
            print(f"   📄 Debug form HTML saved to: {debug_path}")
        except Exception:
            pass

        # Dump available inputs/buttons for debugging
        try:
            fields = await frame.evaluate(
                "Array.from(document.querySelectorAll('input,select,button,a[href]')).map("
                "e=>({tag:e.tagName,name:e.name||'',id:e.id||'',type:e.type||'',text:(e.innerText||e.value||'').trim().substring(0,60)}))"
            )
            print(f"   🔎 Form has {len(fields)} interactive elements")
            for f in fields[:30]:
                print(f"      {f}")
        except Exception:
            pass

        count = 0
        for q in queries:
            count += 1
            if limit and count > limit:
                break

            safe_period = (q.period or "unknown").strip() or "unknown"
            safe_book = (q.book or "cpe").strip() or "cpe"
            base_name = f"{q.ruc_emisor}-{q.tipo}-{q.serie}-{q.numero}"
            out_path = out_base / safe_period / safe_book / base_name
            debug_dir = out_base / safe_period / safe_book / "debug"

            # Check if frame detached or reloaded
            try:
                if frame.is_detached():
                    print("   ⚠️ Frame detached, re-navigating to menu...")
                    page, frame = await _navigate_to_consulta_cpe(page)
            except Exception:
                pass

            # Skip already downloaded
            if skip_existing:
                if any(out_path.with_suffix(ext).exists() for ext in (".xml", ".XML", ".pdf", ".PDF")):
                    results.append(_result_dict(q, "skipped"))
                    continue

            try:
                saved = await _search_individual(
                    page=page,
                    frame=frame,
                    query=q,
                    out_path=out_path,
                    prefer=prefer,
                    debug_dir=debug_dir,
                )

                if saved:
                    results.append(_result_dict(q, "ok", path=str(saved)))
                    print(f"🎉 Saved: {saved}")
                else:
                    results.append(_result_dict(q, "not_found"))
                    print(f"⚠️ Not found / no download: {base_name}")

                # Clear the form for the next query
                await _clear_form(frame, page=page)

            except Exception as e:
                results.append(_result_dict(q, "error", error=str(e)))
                print(f"❌ Error: {e}")
                # Try to recover by clearing form
                try:
                    await _clear_form(frame, page=page)
                except Exception:
                    pass

        await browser.close()

    return results


def _result_dict(
    q: CpeQuery,
    status: str,
    path: str = "",
    error: str = "",
) -> dict:
    return {
        "status": status,
        "ruc_emisor": q.ruc_emisor,
        "tipo": q.tipo,
        "serie": q.serie,
        "numero": q.numero,
        "period": q.period,
        "book": q.book,
        "path": path,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Standalone single-document mode (for manual testing)
# ---------------------------------------------------------------------------

async def run(ruc_emisor, tipo, serie, numero, importe, fecha):
    """Download a single CPE – standalone mode for testing."""
    q = CpeQuery(
        ruc_emisor=ruc_emisor,
        tipo=tipo,
        serie=serie,
        numero=numero,
        importe=importe,
        fecha=fecha,
    )
    results = await run_batch(
        [q],
        outdir=os.path.join(os.path.dirname(__file__), "downloads"),
        prefer="xml",
        headless=False,
        skip_existing=False,
        limit=0,
    )
    for r in results:
        print(r)


if __name__ == "__main__":
    if len(sys.argv) < 7:
        print("Usage: python download_xml_scraper.py <ruc> <tipo> <serie> <num> <imp> <fecha>")
        sys.exit(1)

    asyncio.run(run(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]))
