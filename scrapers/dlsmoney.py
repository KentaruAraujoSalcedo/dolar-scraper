from playwright.async_api import async_playwright
import asyncio
import re

async def scrap_dlsmoney():
    url = "https://dlsmoney.com/"
    casa = "DLS Money"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto(url, timeout=60000)

            # Esperar a que ambas tasas aparezcan y no sean '----'
            await page.wait_for_function(
                """() => {
                    const compra = document.querySelector('.purchase-rate')?.textContent?.trim() || '';
                    const venta = document.querySelector('.sale-rate')?.textContent?.trim() || '';
                    return compra.match(/\\d+\\.\\d+/) && venta.match(/\\d+\\.\\d+/);
                }""",
                timeout=20000
            )

            # Obtener textos
            compra_text = await page.locator(".purchase-rate").text_content()
            venta_text = await page.locator(".sale-rate").text_content()

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
    resultado = asyncio.run(scrap_dlsmoney())
    print(resultado)
