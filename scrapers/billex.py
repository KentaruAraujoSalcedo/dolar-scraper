from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

async def scrap_billex():
    url = "https://www.billex.pe/"
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Espera a que ambos existan
            await page.wait_for_selector("#value-buy", timeout=15000)
            await page.wait_for_selector("#value-sell", timeout=15000)

            # ⚠️ Billex (según DOM actual): value-sell aparece bajo "COMPRA"
            compra_text = (await page.locator("#value-sell").text_content() or "").strip()
            venta_text  = (await page.locator("#value-buy").text_content() or "").strip()

            compra = normalize_rate(compra_text)
            venta  = normalize_rate(venta_text)

            return {
                "casa": "Billex",
                "url": url,
                "compra": compra,
                "venta": venta,
            }

    except Exception as e:
        return {
            "casa": "Billex",
            "url": url,
            "compra": None,
            "venta": None,
            "error": f"No se pudo scrapear: {e}",
        }
    finally:
        if browser:
            await browser.close()
