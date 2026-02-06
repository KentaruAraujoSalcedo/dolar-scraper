from playwright.async_api import async_playwright
import asyncio
import re

async def scrap_cambiosol():
    url = "https://cambiosol.pe/"
    casa = "CambioSol"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Espera que aparezcan los elementos con las tasas
            await page.wait_for_selector("#buy-rate-display", timeout=15000)
            await page.wait_for_selector("#sell-rate-display", timeout=15000)

            compra_raw = await page.locator("#buy-rate-display").text_content()
            venta_raw = await page.locator("#sell-rate-display").text_content()

            # Extraer solo números con punto decimal
            compra = float(re.sub(r"[^\d.]", "", compra_raw or "0"))
            venta = float(re.sub(r"[^\d.]", "", venta_raw or "0"))

            # Validación de tasas falsas (por ejemplo "0.00")
            if compra == 0.0 or venta == 0.0:
                raise ValueError("Las tasas parecen no haber cargado correctamente (0.0)")

            await browser.close()

            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }

# Test manual
if __name__ == "__main__":
    resultado = asyncio.run(scrap_cambiosol())
    print(resultado)
