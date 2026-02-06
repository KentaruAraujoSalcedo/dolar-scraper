from playwright.async_api import async_playwright
import re

async def scrap_cambiox():
    url = "https://cambiox.pe/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            await page.wait_for_selector("span.bold", timeout=10000)

            spans = await page.locator("span.bold").all_text_contents()
            texto_tasa = next((s for s in spans if "Compra" in s and "Venta" in s), None)

            if not texto_tasa:
                raise Exception("No se encontró el texto con tasas.")

            match = re.search(r"Compra:\s*([\d.]+)\s*-\s*Venta:\s*([\d.]+)", texto_tasa)
            if not match:
                raise Exception("No se pudo extraer tasas con regex")

            compra = float(match.group(1))
            venta = float(match.group(2))

            await browser.close()

            return {
                "casa": "CambioX",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "CambioX",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
