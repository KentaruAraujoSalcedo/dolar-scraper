from playwright.async_api import async_playwright
import re

async def scrap_dollarhouse():
    url = "https://app.dollarhouse.pe/"
    casa = "DollarHouse"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Espera a que cargue un texto visible que sabemos que es confiable
            await page.wait_for_selector("text=Tipo de cambio", timeout=20000)

            # Captura todos los span con texto que incluya los valores
            all_spans = await page.locator("span, div, strong").all_text_contents()
            tasas = [s for s in all_spans if re.match(r"3\.\d{4}", s)]


            if len(tasas) < 2:
                raise Exception("No se encontraron suficientes tasas válidas")

            compra = float(tasas[0])
            venta = float(tasas[1])

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

# Test
if __name__ == "__main__":
    import asyncio
    resultado = asyncio.run(scrap_dollarhouse())
    print(resultado)
