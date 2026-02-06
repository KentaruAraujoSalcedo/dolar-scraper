# scrapers/cambiomas.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate


def _extract_numbers(text: str):
    """Devuelve lista de strings numéricas tipo 3.345 / 3,36 encontradas en el texto."""
    if not text:
        return []
    return re.findall(r"\d+[.,]\d+", text)


async def scrap_cambiomas():
    casa = "CambioMas"
    url = "https://cambiosmass.com/"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Espera el bloque donde están Compra/Venta
            await page.wait_for_selector("div.page_sectionCotiza__e2_eF", timeout=25000)

            # Dentro de ese bloque, suelen haber 2 <b> con los números (compra y venta)
            bs = page.locator("div.page_sectionCotiza__e2_eF b")
            await bs.first.wait_for(state="visible", timeout=25000)

            values = []
            for i in range(await bs.count()):
                t = (await bs.nth(i).inner_text() or "").strip()
                values.extend(_extract_numbers(t))

            # A veces los números están en un <p> completo; fallback por si acaso
            if len(values) < 2:
                block_text = await page.locator("div.page_sectionCotiza__e2_eF").inner_text()
                values = _extract_numbers(block_text)

            if len(values) < 2:
                raise Exception(f"No se encontraron 2 tasas. Encontré: {values}")

            compra = normalize_rate(values[0].replace(",", "."))
            venta  = normalize_rate(values[1].replace(",", "."))

            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "error": f"No se pudo scrapear: {e}",
        }
    finally:
        if browser:
            await browser.close()
