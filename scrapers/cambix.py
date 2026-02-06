from playwright.async_api import async_playwright
import asyncio
import re

async def scrap_cambix():
    url = "https://cambix.com.pe/"
    casa = "Cambix"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Esperar que ambos elementos estén visibles
            await page.wait_for_selector(".tipo-cambio__campo__monto", timeout=15000)

            # Capturar todos los valores
            tasas = await page.locator(".tipo-cambio__campo__monto").all_text_contents()

            # Filtrar y limpiar valores con "S/"
            valores = [re.sub(r"[^\d.]", "", t) for t in tasas if "S/" in t]

            if len(valores) < 2:
                raise Exception("No se encontraron suficientes tasas válidas")

            compra = float(valores[0])
            venta = float(valores[1])

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
    resultado = asyncio.run(scrap_cambix())
    print(resultado)
