from playwright.async_api import async_playwright
import asyncio

async def scrap_x_cambio():
    url = "https://x-cambio.com/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Esperamos los elementos visibles
            await page.wait_for_selector("#cambio-compra")
            await page.wait_for_selector("#cambio-venta")

            # Extraemos los valores
            compra_str = await page.locator("#cambio-compra").inner_text()
            venta_str = await page.locator("#cambio-venta").inner_text()

            compra = float(compra_str.strip())
            venta = float(venta_str.strip())

            await browser.close()

            return {
                "casa": "X-Cambio",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "X-Cambio",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }

# Ejecutar la función (puedes integrarla a tu run_scrapers.py)
if __name__ == "__main__":
    resultado = asyncio.run(scrap_x_cambio())

