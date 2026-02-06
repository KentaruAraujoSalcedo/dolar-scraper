from playwright.async_api import async_playwright
import asyncio

async def scrap_zonadolar():
    url = "https://zonadolar.pe/"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            await page.wait_for_selector(".text-base", timeout=15000)

            textos = await page.locator(".text-base").all_text_contents()
            tasas = [t.strip() for t in textos if t.strip().startswith("3.")]

            if len(tasas) < 2:
                raise Exception("No se encontraron tasas suficientes")

            compra = float(tasas[0])
            venta = float(tasas[1])

            await browser.close()

            return {
                "casa": "ZonaDólar",
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": "ZonaDólar",
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }

# Si deseas probarlo directamente:
# asyncio.run(scrap_zonadolar())
