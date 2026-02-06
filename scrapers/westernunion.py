from playwright.async_api import async_playwright

async def scrap_westernunion():
    url = "https://www.westernunionperu.pe/cambiodemoneda"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            # Esperar a que ambos botones estén presentes
            await page.wait_for_selector("#btnCompra", timeout=15000)
            await page.wait_for_selector("#btnVenta", timeout=15000)

            compra_text = await page.locator("#btnCompra").text_content()
            venta_text = await page.locator("#btnVenta").text_content()

            compra = float(compra_text.strip())
            venta = float(venta_text.strip())

            await browser.close()

            return {
                "casa": "WesternUnion",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "WesternUnion",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
