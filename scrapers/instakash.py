from playwright.async_api import async_playwright

async def scrap_instakash():
    url = "https://instakash.net/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            # Espera solo a los bloques que contienen las tasas
            await page.wait_for_selector("div.flex.items-center.justify-center .font-semibold", timeout=15000)

            # Obtiene solo esos valores de compra/venta
            tasas = await page.locator("div.flex.items-center.justify-center .font-semibold").all_text_contents()
            
            # Limpieza
            compra = float(tasas[0].replace("S/", "").strip())
            venta = float(tasas[1].replace("S/", "").strip())

            await browser.close()

            return {
                "casa": "Instakash",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "Instakash",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
