from playwright.async_api import async_playwright

async def scrap_smartdollar():
    url = "https://www.smartdollar.pe/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            # No hacemos wait_for_selector, accedemos directamente
            compra_text = await page.locator(".cantant").nth(0).text_content()
            venta_text = await page.locator(".cantant").nth(1).text_content()

            compra = float(compra_text.strip())
            venta = float(venta_text.strip())

            await browser.close()

            return {
                "casa": "SmartDollar",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "SmartDollar",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
