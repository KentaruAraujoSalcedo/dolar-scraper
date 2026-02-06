from playwright.async_api import async_playwright
import re

async def scrap_securex():
    url = "https://securex.pe/"
    casa = "Securex"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Espera a que carguen los contenedores de compra y venta
            await page.wait_for_selector("#item_compra span[style]", timeout=15000)
            await page.wait_for_selector("#item_venta span[style]", timeout=15000)

            # Extrae los valores
            compra_text = await page.locator("#item_compra span[style]").text_content()
            venta_text = await page.locator("#item_venta span[style]").text_content()

            compra = float(re.sub(r"[^\d.]", "", compra_text))
            venta = float(re.sub(r"[^\d.]", "", venta_text))

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
    import asyncio
    resultado = asyncio.run(scrap_securex())
    print(resultado)
