import asyncio
from playwright.async_api import async_playwright

async def scrap_yanki():
    url = "https://yanki.pe"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=20000)
            await page.wait_for_selector("#DolarCompra", timeout=10000)
            await page.wait_for_selector("#DolarVenta", timeout=10000)

            compra = await page.locator("#DolarCompra").text_content()
            venta = await page.locator("#DolarVenta").text_content()

            await browser.close()

            return {
                "casa": "Yanki",
                "url": url,
                "compra": float(compra.strip()),
                "venta": float(venta.strip())
            }

    except Exception as e:
        return {
            "casa": "Yanki",
            "url": url,
            "error": f"No se pudo scrapear (Playwright async): {str(e)}"
        }
