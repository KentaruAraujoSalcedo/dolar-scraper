from playwright.async_api import async_playwright

async def scrap_okane():
    url = "https://okanecambiodigital.com/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)
            await page.wait_for_selector(".cant", timeout=10000)

            valores = await page.locator(".cant").all_text_contents()

            # Limpieza: eliminar símbolos y convertir a float
            compra = float(valores[0].strip().replace(",", "."))
            venta = float(valores[1].strip().replace(",", "."))

            await browser.close()

            return {
                "casa": "Okane",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "Okane",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
