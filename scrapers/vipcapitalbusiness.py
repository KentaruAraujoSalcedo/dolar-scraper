from playwright.async_api import async_playwright
import re
from scrapers.utils import normalize_rate

async def scrap_vipcapitalbusiness():
    url = "https://www.vipcapitalbusiness.com/"
    casa = "VipCapital"

    def _clean(txt: str) -> str:
        return re.sub(r"[^\d.,]", "", (txt or "")).replace(",", ".")

    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            await page.wait_for_selector("#tc_compra", timeout=30000)
            await page.wait_for_selector("#tc_venta",  timeout=30000)

            compra_raw = (await page.locator("#tc_compra").text_content()) or ""
            venta_raw  = (await page.locator("#tc_venta").text_content()) or ""

            compra = normalize_rate(_clean(compra_raw))
            venta  = normalize_rate(_clean(venta_raw))

            # Si la web muestra 0.000/0.000 -> cerrado (no es error)
            cerrado = ("0.000" in compra_raw and "0.000" in venta_raw) or (compra is None and venta is None)

            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
                "estado": "cerrado" if cerrado else "abierto",
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
    finally:
        if browser:
            await browser.close()
