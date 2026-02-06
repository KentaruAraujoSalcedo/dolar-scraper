from playwright.async_api import async_playwright
import re

async def scrap_perudolar():
    url = "https://perudolar.pe/"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)
            await page.wait_for_selector("#preciosHome", timeout=15000)

            text = await page.locator("#preciosHome").inner_text()

            # Extraer con regex
            match = re.search(r"Compra:\s*([\d.]+)\s*\|\s*Venta:\s*([\d.]+)", text)
            if not match:
                raise Exception("No se pudo extraer las tasas del texto")

            compra = float(match.group(1))
            venta = float(match.group(2))

            await browser.close()

            return {
                "casa": "PeruDolar",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "PeruDolar",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }
