from playwright.async_api import async_playwright
import asyncio

async def scrap_rissanpe():
    url = "https://www.rissanpe.com/"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Espera que el contenido con el texto de compra y venta esté visible
            await page.wait_for_selector("h2.elementor-heading-title")

            # Extrae todos los textos que contienen los valores
            elementos = await page.locator("h2.elementor-heading-title").all_text_contents()

            # Filtra los que contienen "Compra" y "Venta"
            compra = None
            venta = None
            for texto in elementos:
                if "Compra" in texto:
                    compra = float(texto.split("S/")[-1].strip())
                elif "Venta" in texto:
                    venta = float(texto.split("S/")[-1].strip())

            await browser.close()

            if compra is not None and venta is not None:
                return {
                    "casa": "RissanPE",
                    "url": url,
                    "compra": compra,
                    "venta": venta
                }
            else:
                raise ValueError("No se encontraron tasas válidas")

    except Exception as e:
        return {
            "casa": "RissanPE",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }

# Para pruebas rápidas
# asyncio.run(scrap_rissanpe())
