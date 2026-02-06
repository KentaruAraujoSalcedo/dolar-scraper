from playwright.async_api import async_playwright

async def scrap_tkambio():
    url = "https://tkambio.com/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            # Esperar todos los spans con clase price
            await page.wait_for_selector("span.price", timeout=15000)
            precios = page.locator("span.price")
            count = await precios.count()

            if count < 2:
                raise Exception("No se encontraron suficientes precios.")

            compra_text = await precios.nth(0).text_content()
            venta_text = await precios.nth(1).text_content()

            await browser.close()

            return {
                "casa": "Tkambio",
                "url": url,
                "compra": float(compra_text.strip()),
                "venta": float(venta_text.strip())
            }

    except Exception as e:
        return {
            "casa": "Tkambio",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
