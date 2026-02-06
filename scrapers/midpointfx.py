from playwright.async_api import async_playwright

async def scrap_midpointfx():
    url = "https://www.midpointfx.com/"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("span.wixui-rich-text__text", timeout=15000)

            spans = await page.locator("span.wixui-rich-text__text").all_text_contents()
            

            # Filtrar solo los que parezcan tasas válidas (ej. 3.520)
            tasas = [s.strip() for s in spans if s.replace('.', '', 1).isdigit()]

            # Filtrar duplicados y tomar los dos primeros únicos
            tasas_unicas = list(dict.fromkeys(tasas))  # elimina duplicados manteniendo orden

            if len(tasas_unicas) < 2:
             raise Exception("No se encontraron suficientes tasas únicas")

            compra = float(tasas_unicas[0])
            venta = float(tasas_unicas[1])


            await browser.close()
            return {
                "casa": "MidpointFX",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "MidpointFX",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
