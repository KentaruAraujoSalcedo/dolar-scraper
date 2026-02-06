from playwright.async_api import async_playwright
import asyncio

async def scrap_dolarex():
    url = "https://dolarex.pe/"
    casa = "Dolarex"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Espera hasta que ambos valores aparezcan
            await page.wait_for_selector(".compra .valor", timeout=15000)
            await page.wait_for_selector(".venta .valor", timeout=15000)

            compra_text = await page.locator(".compra .valor").text_content()
            venta_text = await page.locator(".venta .valor").text_content()

            compra = float(compra_text.strip())
            venta = float(venta_text.strip())

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
    resultado = asyncio.run(scrap_dolarex())
    print(resultado)
