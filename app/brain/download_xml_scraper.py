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
from typing import Iterable, Literal, Optional, List

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
    ruc_cliente: str = "" # Required for multi-tenant sessions
    razon_social_cliente: str = "" # Required for folder naming


# ---------------------------------------------------------------------------
# Cookie / session helpers
# ---------------------------------------------------------------------------

def _load_sunat_session_cookies(ruc: str) -> list[dict]:
    cookie_file = os.path.join(os.path.dirname(__file__), f"sunat_session_{ruc}.json")
    if not os.path.exists(cookie_file):
        # Fallback to default for backwards compatibility
        cookie_file = os.path.join(os.path.dirname(__file__), "sunat_session.json")
        if not os.path.exists(cookie_file):
            raise FileNotFoundError(
                f"Session file for RUC {ruc} not found. Run automation_scraper.py --ruc {ruc} first."
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
                print(f"   Overlay detected: {sel}. Removing…")
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
    print("Navigating to Consulta de Comprobantes de Pago…")
    await page.wait_for_load_state("networkidle")
    await _dismiss_overlays(page)

    old_pages = list(page.context.pages)
    # Click the menu item natively using jQuery (to trigger their exact internal routing)
    try:
        await page.evaluate("$('#nivel4_11_38_1_1_1').click()")
    except Exception as e:
        print(f"   JS click() raised: {e}")

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
    print(f"   Filtering: {fecha_desde} – {fecha_hasta} | RUC: {ruc}")

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
    out_dir: Path,
    base_name: str,
    prefer: DownloadPrefer,
    debug_dir: Optional[Path] = None,
    tmp_downloads_dir: Optional[Path] = None,
) -> List[Path]:
    """Fill the individual CPE search form, check results, and download.

    This function handles the 'Consulta Individual' tab inside the
    Consulta de Comprobantes page.
    """
    print(f"Query: {base_name}")

    # Check if we are in the new Angular form by looking for 'rucEmisor' formcontrolname
    is_angular = await frame.locator("input[formcontrolname='rucEmisor']").count() > 0

    if is_angular:
        try:
            if query.book == "sales":
                await frame.locator("#emitido").check(force=True)
                await asyncio.sleep(0.5)
                try:
                    await frame.locator("input[formcontrolname='rucReceptor']").fill(query.ruc_emisor, timeout=2000)
                except Exception:
                    pass
            else:
                await frame.locator("#recibido").check(force=True)
                await asyncio.sleep(0.5)
                try:
                    await frame.locator("input[formcontrolname='rucEmisor']").fill(query.ruc_emisor, timeout=2000)
                except Exception:
                    pass
        except Exception as e:
            print(f"   Could not configure Recibido/Emitido and fill RUC: {e}")

        # 3. Tipo Comprobante (PrimeNG dropdown)
        # Bug Fix 1 & 2: mapeo extendido de tipos + timeouts aumentados
        try:
            dropdown = frame.locator("p-dropdown[formcontrolname='tipoComprobanteI']")
            await dropdown.click(timeout=5000)  # Bug 2: aumentado de 2000 a 5000ms

            # Bug 2: esperar explícitamente a que el panel de opciones sea visible
            try:
                await frame.wait_for_selector(
                    "p-dropdownitem li", state="visible", timeout=4000
                )
            except Exception:
                pass

            await asyncio.sleep(0.5)

            tipo_str = str(query.tipo).strip().zfill(2)
            serie_str = str(query.serie).strip().upper()

            # Bug 1: Catálogo completo de tipos de comprobante SUNAT (Catálogo N° 01)
            TIPO_TEXT_MAP = {
                "01": "Factura",
                "02": "Recibo por Honorarios",
                "03": "Boleta de Venta",
                "04": "Liquidación de compra",
                "05": "Boleto de compañía de aviación",
                "06": "Carta de porte aéreo",
                "07": "Nota de Crédito",   # se refina abajo según serie
                "08": "Nota de Débito",    # se refina abajo según serie
                "09": "Guía de remisión remitente",
                "10": "Recibo por arrendamiento",
                "11": "Póliza de adjudicación",
                "12": "Ticket o cinta emitida por máquina registradora",
                "13": "Documentos emitidos por bancos",
                "14": "Recibo por servicios públicos",
                "15": "Boletos emitidos por servicios de transporte",
                "16": "Boletos emitidos por espectáculos públicos",
                "17": "Documento de atribución",
                "18": "Documentos emitidos por AFP",
                "19": "Boleto o entrada por atracciones",
                "20": "Comprobante de retención",
                "21": "Conocimiento de embarque",
                "22": "Comprobante por Operaciones No Habituales",
                "23": "Póliza de seguro",
                "24": "Certificado de renta",
                "25": "Ticket de transporte ferroviario",
                "26": "Recibo de gas natural",
                "27": "Factura negociable",
                "28": "Tarjeta de crédito",
                "29": "Certificado de depósito",
                "30": "Liquidación de compra",  # Bug 1: tipo 30 no estaba mapeado
                "31": "Guía de remisión transportista",
                "34": "Documento del operador",
                "35": "Documento del partícipe",
                "36": "Recibo de haber",
                "37": "Documentos sustentatorios de operaciones de importación",
                "40": "Comprobante de percepción",
                "41": "Comprobante de retención electrónico",
                "50": "Declaración Única de Aduanas (Importación definitiva)",
                "52": "Despacho simplificado (Importación)",
                "53": "Declaración de mensajería",
                "56": "Declaración Única de Aduanas (Exportación definitiva)",
                "87": "Nota de crédito especial",
                "88": "Nota de débito especial",
                "91": "Comprobante de no domiciliado",
                "96": "Exceso de crédito fiscal por tasa adicional del IGV",
                "97": "Nota de crédito - no domiciliado",
                "98": "Nota de débito - no domiciliado",
            }

            # Refinar tipos 07 y 08 según la letra de la serie
            if tipo_str == "07":
                if serie_str.startswith("B"):
                    exact_text = "Boleta de Venta - Nota de Crédito"
                else:
                    exact_text = "Factura - Nota de Crédito"
            elif tipo_str == "08":
                if serie_str.startswith("B"):
                    exact_text = "Boleta de Venta - Nota de Débito"
                else:
                    exact_text = "Factura - Nota de Débito"
            else:
                exact_text = TIPO_TEXT_MAP.get(tipo_str, "")

            selected = False
            if exact_text:
                # Intento 1: coincidencia exacta
                item_loc = frame.locator(f"p-dropdownitem li:text-is('{exact_text}')")
                if await item_loc.count() > 0:
                    await item_loc.first.click(timeout=4000)
                    selected = True

                if not selected:
                    # Intento 2: coincidencia parcial
                    fallback_loc = frame.locator(f"p-dropdownitem li:has-text('{exact_text}')")
                    if await fallback_loc.count() > 0:
                        await fallback_loc.first.click(timeout=4000)
                        selected = True

            if not selected:
                # Intento 3 (Bug 1 fallback): buscar por el código numérico directamente en el texto
                code_loc = frame.locator(f"p-dropdownitem li:has-text('{tipo_str}')")
                if await code_loc.count() > 0:
                    await code_loc.first.click(timeout=4000)
                    selected = True
                    print(f"   Tipo {tipo_str} seleccionado por código (fallback).")

            if not selected:
                print(f"   WARN: No se pudo seleccionar tipo {tipo_str} ('{exact_text}') en el dropdown. Continuando sin filtro de tipo.")
                await frame.evaluate("document.body.click()")

        except Exception as e:
            print(f"   Could not select tipoComprobante: {e}")

        # 4. Serie & Numero
        try:
            await frame.locator("input[formcontrolname='serieComprobante']").fill(query.serie, timeout=2000)
            await frame.locator("input[formcontrolname='numeroComprobante']").fill(query.numero, timeout=2000)
        except Exception as e:
            print(f"   Could not fill serie/numero: {e}")
            
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
                print(f"   Could not fill {name}: {e}")

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
        return []

    print(f"   Found: {base_name}")
    
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

    if prefer in ("xml", "either"):
        # Check XML selectors
        for sel in xml_sels:
            try:
                if await frame.locator(sel).count() > 0:
                    targets.append(("xml", frame.locator(sel).first))
                    break
            except Exception:
                continue

    if prefer in ("pdf", "either"):
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
        print(f"   Comprobante found but NO download button available")
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
        return []

    # Download the files
    downloaded_paths = []
    
    for file_type, target in targets:
        try:
            import time
            import shutil
            
            # SNAPSHOT: record what's already in tmp BEFORE clicking
            # This prevents picking up leftover files from a previous query
            existing_in_tmp = set()
            if tmp_downloads_dir and tmp_downloads_dir.exists():
                existing_in_tmp = {f.name for f in tmp_downloads_dir.glob("*")}
            
            # AUMENTAMOS EL TIMEOUT A 30 SEGUNDOS (30000ms) PORQUE SUNAT ES LENTO CON LOS ZIP
            download_task = asyncio.ensure_future(
                page.context.wait_for_event("download", timeout=30000)
            )

            await target.click()
            
            # Check for the warning modal "El archivo se ha descargado previamente"
            try:
                accept_btn = frame.locator("button:has-text('Aceptar'), .swal2-confirm")
                if await accept_btn.count() > 0:
                    await accept_btn.first.click(timeout=2000)
            except Exception:
                pass
                
            # Active polling loop for Chromium silent downloads
            recovered = False
            start_wait = time.time()
            
            # AUMENTAMOS EL BUCLE A 30 SEGUNDOS
            while time.time() - start_wait < 30: 
                if download_task.done() and not download_task.cancelled() and not isinstance(download_task.exception(), Exception):
                    break # The official download event fired!
                    
                if tmp_downloads_dir and tmp_downloads_dir.exists():
                    files = list(tmp_downloads_dir.glob("*"))
                    # KEY FIX: Only consider files that WEREN'T there before we clicked
                    new_files = [f for f in files if f.name not in existing_in_tmp]
                    if new_files:
                        new_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        newest = new_files[0]
                        # Check: not a temp file, and size > 1KB (fully written)
                        file_stat = newest.stat()
                        if not newest.name.endswith('.crdownload') and file_stat.st_size > 1024:
                            
                            # SOLUCIÓN: Detectar la extensión real (sea .zip, .xml, o .pdf)
                            ext_real = newest.suffix.lower()
                            if not ext_real or ext_real == '.bin':
                                ext_real = f".{file_type}" if file_type != "fallback" else ".pdf"

                            # Rutear a la carpeta correcta basado en la extensión real
                            if ext_real in (".xml", ".zip"):
                                subfolder = "xml"
                            elif ext_real == ".pdf":
                                subfolder = "pdf"
                            else:
                                subfolder = "pdf" if file_type in ("pdf", "fallback") else "xml"
                                
                            final_dir = out_dir / subfolder
                            final_dir.mkdir(parents=True, exist_ok=True)
                            final_path = final_dir / f"{base_name}{ext_real}"
                            
                            shutil.copy2(newest, final_path)
                            
                            # Verify the copy actually worked (not zero bytes)
                            if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                                try:
                                    newest.unlink()
                                except Exception:
                                    pass  # Windows may lock the file - that's OK, it's already copied
                                    
                                downloaded_paths.append(final_path)
                                recovered = True
                                print(f"   Recovered downloaded file actively: {newest.name} -> guardado como {final_path.name}")
                                
                                # Cancel the official wait task since we got the file
                                if not download_task.done():
                                    download_task.cancel()
                                break
                            else:
                                print(f"   Warning: copy of {newest.name} failed or resulted in empty file. Retrying...")
                await asyncio.sleep(1)

            if recovered:
                await asyncio.sleep(0.5)
                continue # move to next target
                
            # If we reach here and it's not recovered, maybe the official download event succeeded
            try:
                download = await download_task
                suggested = download.suggested_filename or "download"
                
                # SOLUCIÓN: Respetar la extensión del archivo oficial sugerido por SUNAT
                ext = os.path.splitext(suggested)[1] or f".{file_type}"
                
                if ext.lower() == ".bin" and file_type != "fallback":
                    ext = f".{file_type}"
                    
                ext_lower = ext.lower()
                
                # Rutear a la carpeta correcta
                if ext_lower in (".xml", ".zip"):
                    subfolder = "xml"
                elif ext_lower == ".pdf":
                    subfolder = "pdf"
                else:
                    subfolder = "pdf" if file_type in ("pdf", "fallback") else "xml"
                    
                final_dir = out_dir / subfolder
                final_dir.mkdir(parents=True, exist_ok=True)
                
                final_path = final_dir / f"{base_name}{ext}"
                await download.save_as(str(final_path))
                downloaded_paths.append(final_path)
                print(f"   Downloaded officially: {final_path.name}")
                await asyncio.sleep(0.5)
            except Exception as wait_err:
                print(f"   Download failed for {file_type}: Timeout or error -> {wait_err}")

        except Exception as e:
            print(f"   Download click or process failed for {file_type}: {e}")
            
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
        return []

    return downloaded_paths


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
import re

def _sanitize_folder_name(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

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
    out_base = Path(outdir).expanduser().resolve()
    results: list[dict] = []

    # Group queries by ruc_cliente so we can load the correct session cookie
    from collections import defaultdict
    queries_by_client = defaultdict(list)
    for q in queries:
        queries_by_client[q.ruc_cliente].append(q)

    async with async_playwright() as p:
        tmp_downloads_dir = out_base / "tmp_downloads"
        tmp_downloads_dir.mkdir(parents=True, exist_ok=True)
        browser = await p.chromium.launch(headless=headless, downloads_path=str(tmp_downloads_dir))
        
        for ruc_cliente, client_queries in queries_by_client.items():
            print(f"\n--- Processing {len(client_queries)} queries for client {ruc_cliente} ---")
            
            try:
                cookies = _load_sunat_session_cookies(ruc_cliente)
            except FileNotFoundError as e:
                print(f"Error: {e}")
                for q in client_queries:
                    results.append(_result_dict(q, "error", error="No session cookies found"))
                continue

            context = await browser.new_context(
                user_agent=_default_user_agent(),
                accept_downloads=True,
            )
            await context.add_cookies(cookies)

            page = await context.new_page()
            print(f"Navigating to SUNAT Main Menu for {ruc_cliente}…")
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
                print(f"   Debug form HTML saved to: {debug_path}")
            except Exception:
                pass

            # Dump available inputs/buttons for debugging
            try:
                fields = await frame.evaluate(
                    "Array.from(document.querySelectorAll('input,select,button,a[href]')).map("
                    "e=>({tag:e.tagName,name:e.name||'',id:e.id||'',type:e.type||'',text:(e.innerText||e.value||'').trim().substring(0,60)}))"
                )
                print(f"   Form has {len(fields)} interactive elements")
                for f in fields[:30]:
                    print(f"      {f}")
            except Exception:
                pass

            count = 0
            for q in client_queries:
                count += 1
                if limit and count > limit:
                    break

                safe_period = (q.period or "unknown").strip() or "unknown"
                safe_book = (q.book or "cpe").strip() or "cpe"
                # Bug 3: cuando ruc_emisor está vacío (ej. boletas de venta propias),
                # usar ruc_cliente como identificador para evitar nombre "--03-EB01-XXXX"
                ruc_for_name = (q.ruc_emisor or "").strip() or (q.ruc_cliente or "").strip() or "SIN_RUC"
                base_name = f"{ruc_for_name}-{q.tipo}-{q.serie}-{q.numero}"
                
                safe_ruc_cliente = q.ruc_cliente or "unknown_ruc"
                safe_rs_cliente = _sanitize_folder_name(q.razon_social_cliente) if q.razon_social_cliente else "Empresa"
                folder_client = f"{safe_rs_cliente} {safe_ruc_cliente}".strip()
                
                out_dir = out_base / folder_client / safe_period / safe_book
                debug_dir = out_dir / "debug"

                # Check if frame detached or reloaded
                try:
                    if frame.is_detached():
                        print("   Frame detached, re-navigating to menu...")
                        page, frame = await _navigate_to_consulta_cpe(page)
                except Exception:
                    pass

                # Skip already downloaded
                if skip_existing:
                    xml_path = out_dir / "xml" / f"{base_name}.xml"
                    zip_path = out_dir / "xml" / f"{base_name}.zip"
                    pdf_path = out_dir / "pdf" / f"{base_name}.pdf"
                    
                    if xml_path.exists() or zip_path.exists() or pdf_path.exists():
                        # We will prioritize returning the XML path if it exists
                        existing_path = xml_path if xml_path.exists() else (zip_path if zip_path.exists() else pdf_path)
                        results.append(_result_dict(q, "skipped", path=str(existing_path)))
                        continue

                try:
                    saved = await _search_individual(
                        page=page,
                        frame=frame,
                        query=q,
                        out_dir=out_dir,
                        base_name=base_name,
                        prefer=prefer,
                        debug_dir=debug_dir,
                        tmp_downloads_dir=tmp_downloads_dir,
                    )

                    if saved:
                        # Bug 4: pasar lista de paths guardados
                        results.append(_result_dict(q, "ok", paths=[str(p) for p in saved]))
                        print(f"Saved: {saved}")
                    else:
                        results.append(_result_dict(q, "not_found"))
                        print(f"Not found / no download: {base_name}")

                    # Clear the form for the next query
                    await _clear_form(frame, page=page)

                except Exception as e:
                    results.append(_result_dict(q, "error", error=str(e)))
                    print(f"Error: {e}")
                    # SUNAT a veces se congela o entra en bucle.
                    # Para recuperarnos, recargamos la página por completo y volvemos a abrir el menú.
                    try:
                        print("   La página parece haberse congelado. Recargando el navegador...")
                        await page.reload()
                        await asyncio.sleep(3)
                        page, frame = await _navigate_to_consulta_cpe(page)
                    except Exception as e2:
                        print(f"   Fallo al recargar la página: {e2}")
            
            # Close context for this client
            await context.close()

        await browser.close()

    return results


def _result_dict(
    q: CpeQuery,
    status: str,
    paths: list = None,
    error: str = "",
) -> dict:
    # Bug 4: normalizado a `paths` (lista) para consistencia con el orchestrator
    return {
        "status": status,
        "ruc_emisor": q.ruc_emisor,
        "tipo": q.tipo,
        "serie": q.serie,
        "numero": q.numero,
        "period": q.period,
        "book": q.book,
        "paths": paths or [],
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
