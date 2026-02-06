# scrapers/cambiodigitalperu.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

def _extract_number(text: str):
    if not text:
        return None
    m = re.search(r"\d+[.,]\d+", text)
    return m.group(0) if m else None

async def scrap_cambiodigitalperu():
    url = "https://cambiodigitalperu.com"
    casa = "CambioDigitalPeru"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            compra_loc = page.locator("#tipoCambioCompra")
            venta_loc  = page.locator("#tipoCambioVenta")

            await compra_loc.wait_for(state="visible", timeout=20000)
            await venta_loc.wait_for(state="visible", timeout=20000)

            # ✅ Espera a que los valores sean “reales” (no el placeholder 3.8 / 3.85)
            await page.wait_for_function(
                """() => {
                    const cTxt = document.querySelector('#tipoCambioCompra')?.textContent?.trim() || '';
                    const vTxt = document.querySelector('#tipoCambioVenta')?.textContent?.trim() || '';

                    const cMatch = cTxt.match(/\\d+[\\.,]\\d+/);
                    const vMatch = vTxt.match(/\\d+[\\.,]\\d+/);

                    if (!cMatch || !vMatch) return false;

                    const c = parseFloat(cMatch[0].replace(',', '.'));
                    const v = parseFloat(vMatch[0].replace(',', '.'));

                    // Ajusta rangos si algún día cambia muchísimo (pero así evita 3.8/3.85)
                    return c >= 3.0 && c <= 3.7 && v >= 3.0 && v <= 3.7;
                }""",
                timeout=30000
            )

            compra_raw = (await compra_loc.text_content() or "").strip()
            venta_raw  = (await venta_loc.text_content() or "").strip()

            compra_num = _extract_number(compra_raw)
            venta_num  = _extract_number(venta_raw)

            compra = normalize_rate(compra_num) if compra_num else None
            venta  = normalize_rate(venta_num) if venta_num else None

            return {"casa": casa, "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": casa, "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}
    finally:
        if browser:
            await browser.close()
