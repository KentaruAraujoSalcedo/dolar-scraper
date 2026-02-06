# scrapers/kambio.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate


def _extract_number(text: str):
    if not text:
        return None
    m = re.search(r"\d+[.,]\d+", text)
    return m.group(0) if m else None


async def scrap_kambio():
    url = "https://www.kambio.online/"
    casa = "Kambio"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # (Opcional) cerrar cookies si sale
            try:
                await page.get_by_role("button", name=re.compile("aceptar|accept", re.I)).click(timeout=2000)
            except Exception:
                pass

            # ✅ En vez de get_by_text("Compro") (strict), vamos directo al <p> correcto
            compra_span = page.locator("p", has_text="Compro").locator("span.font-bold").first
            venta_span  = page.locator("p", has_text="Vendo").locator("span.font-bold").first

            await compra_span.wait_for(state="visible", timeout=25000)
            await venta_span.wait_for(state="visible", timeout=25000)

            compra_raw = (await compra_span.inner_text()).strip()
            venta_raw  = (await venta_span.inner_text()).strip()

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
