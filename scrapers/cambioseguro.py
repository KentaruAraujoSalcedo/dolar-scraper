# scrapers/cambioseguro.py
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

async def scrap_cambioseguro():
    url = "https://cambioseguro.com/"
    casa = "CambioSeguro"
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            # Los valores suelen estar en .value-rate (compra, venta)
            await page.wait_for_selector(".value-rate", timeout=15000)
            valores = await page.locator(".value-rate").all_text_contents()

            # Tolerante a comas, espacios, prefijos
            get_txt = lambda i: (valores[i] if len(valores) > i else "").strip().replace("S/", "").replace("s/", "")
            compra = normalize_rate(get_txt(0))
            venta  = normalize_rate(get_txt(1))

            return {
                "casa": casa,
                "url": url,
                "compra": compra,  # None si 0/ inválido
                "venta":  venta,   # None si 0/ inválido
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
