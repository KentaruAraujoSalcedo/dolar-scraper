from playwright.async_api import async_playwright

async def scrap_intercambialo():
    url = "https://intercambialo.pe/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            await page.wait_for_selector("#tipocompra", timeout=15000)
            await page.wait_for_selector("#tipoventa", timeout=15000)

            compra_text = await page.locator("#tipocompra").text_content()
            venta_text = await page.locator("#tipoventa").text_content()

            compra = float(compra_text.strip())
            venta = float(venta_text.strip())

            await browser.close()

            return {
                "casa": "Intercambialo",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "Intercambialo",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
