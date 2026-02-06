from playwright.async_api import async_playwright

async def scrap_dichikash():
    url = "https://dichikash.com/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)
            
            # Solo esperar que esté en el DOM, no que sea visible
            await page.wait_for_selector("input#numero2", state="attached", timeout=15000)
            await page.wait_for_selector("input#numero3", state="attached", timeout=15000)

            compra_raw = await page.locator("input#numero2").get_attribute("value")
            venta_raw = await page.locator("input#numero3").get_attribute("value")

            compra = float(compra_raw.strip())
            venta = float(venta_raw.strip())

            await browser.close()

            return {
                "casa": "Dichikash",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "Dichikash",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
