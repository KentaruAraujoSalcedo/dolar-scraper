from playwright.async_api import async_playwright
import re

async def scrap_chapacambio():
    url = "https://chapacambio.com/"
    casa = "ChapaCambio"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Esperar hasta que los valores sean numéricos válidos
            await page.wait_for_function("""
                () => {
                    const compra = document.querySelector("span[data-rel='compra']")?.textContent || "";
                    const venta = document.querySelector("span[data-rel='venta']")?.textContent || "";
                    return compra.includes("3.") && venta.includes("3.");
                }
            """, timeout=20000)

            # Extraer los valores
            compra_raw = await page.locator("span[data-rel='compra']").text_content()
            venta_raw = await page.locator("span[data-rel='venta']").text_content()

            compra = float(re.sub(r"[^\d.]", "", compra_raw or "0"))
            venta = float(re.sub(r"[^\d.]", "", venta_raw or "0"))

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
    resultado = asyncio.run(scrap_chapacambio())
    print(resultado)
