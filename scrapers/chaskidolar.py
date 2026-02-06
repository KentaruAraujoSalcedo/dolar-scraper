from playwright.async_api import async_playwright

async def scrap_chaskidolar():
    url = "https://chaskidolar.com/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            # Esperar a que cargue al menos un span con text-black
            await page.wait_for_selector(".text-black", timeout=15000)

            tasas = await page.locator(".text-black").all_text_contents()
           
            # Validación de cantidad de tasas encontradas
            if len(tasas) < 2:
                raise Exception("No se encontraron suficientes valores.")

            # Asignación en orden: venta (posición 0), compra (posición 1)
            venta = float(tasas[0].replace("S/", "").strip())
            compra = float(tasas[1].replace("S/", "").strip())

            await browser.close()

            return {
                "casa": "ChaskiDolar",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "ChaskiDolar",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
