from playwright.async_api import async_playwright

async def scrap_jetperu():
    url = "https://jetperu.com.pe/cambiar-dinero/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)
            await page.wait_for_selector("#buyRate", timeout=15000)
            await page.wait_for_selector("#sellRate", timeout=15000)

            compra_text = await page.locator("#buyRate").text_content()
            venta_text = await page.locator("#sellRate").text_content()

            compra = float(compra_text.strip())
            venta = float(venta_text.strip())

            await browser.close()

            return {
                "casa": "JetPerú",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "JetPerú",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
