from playwright.async_api import async_playwright

async def scrap_megamoney():
    url = "https://megamoney.pe/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            await page.wait_for_selector("span.clickable", timeout=15000)

            tasas = await page.locator("span.clickable").all_text_contents()
           
            # Filtramos solo las que contienen montos
            tasas_filtradas = [t for t in tasas if "Compra" in t or "Venta" in t]
            compra = float(tasas_filtradas[0].split()[-1])
            venta = float(tasas_filtradas[1].split()[-1])

            await browser.close()

            return {
                "casa": "MegaMoney",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "MegaMoney",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
