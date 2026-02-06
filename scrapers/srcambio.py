# scrapers/srcambio.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

def _extract_number(text: str):
    if not text:
        return None
    m = re.search(r"\d+[.,]\d+", text)
    return m.group(0) if m else None

async def scrap_srcambio():
    url = "https://srcambio.pe/"
    casa = "SRCambio"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Espera a que existan los spans con los valores
            compra_el = page.locator("#tipoCambioCompra")
            venta_el = page.locator("#tipoCambioVenta")

            await compra_el.wait_for(state="visible", timeout=25000)
            await venta_el.wait_for(state="visible", timeout=25000)

            # Espera a que ya tengan un número > 0 (a veces cargan luego)
            await page.wait_for_function(
                """() => {
                    const c = document.querySelector('#tipoCambioCompra')?.textContent?.trim() || '';
                    const v = document.querySelector('#tipoCambioVenta')?.textContent?.trim() || '';
                    const cf = parseFloat(c.replace(',', '.'));
                    const vf = parseFloat(v.replace(',', '.'));
                    return Number.isFinite(cf) && Number.isFinite(vf) && cf > 0 && vf > 0;
                }""",
                timeout=25000
            )

            compra_raw = (await compra_el.text_content() or "").strip()
            venta_raw  = (await venta_el.text_content() or "").strip()

            compra_num = _extract_number(compra_raw)
            venta_num  = _extract_number(venta_raw)

            compra = normalize_rate(compra_num) if compra_num else None
            venta  = normalize_rate(venta_num) if venta_num else None

            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "error": f"No se pudo scrapear: {e}",
        }
    finally:
        if browser:
            await browser.close()
