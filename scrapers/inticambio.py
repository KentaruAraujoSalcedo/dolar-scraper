from playwright.async_api import async_playwright
import asyncio
import re

async def scrap_inticambio():
    url = "https://inticambio.pe/"
    casa = "IntiCambio"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Esperar que los spans de compra y venta estén disponibles
            await page.wait_for_selector("#buyRate", timeout=15000)
            await page.wait_for_selector("#sellRate", timeout=15000)

            compra_raw = await page.locator("#buyRate").text_content()
            venta_raw = await page.locator("#sellRate").text_content()

            compra = float(re.search(r"\d+\.\d+", compra_raw).group())
            venta = float(re.search(r"\d+\.\d+", venta_raw).group())

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
    resultado = asyncio.run(scrap_inticambio())
    print(resultado)
