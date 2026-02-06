# scrapers/dinersfx.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

def _extract_rate(text: str):
    """
    Extrae un número tipo 3.3280 o 3,3280 desde un string.
    Devuelve string numérico o None.
    """
    if not text:
        return None
    m = re.search(r"\d+[.,]\d{3,4}", text)
    return m.group(0) if m else None


async def scrap_dinersfx():
    url = "https://dinersfx.pe/"
    casa = "DinersFX"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Esperar a que existan al menos 2 spans de tasas visibles
            # (en tu HTML están como span.font-gotham-book)
            await page.wait_for_selector("span.font-gotham-book", timeout=25000)

            # Esperar a que ya hayan 2 valores numéricos válidos (no None)
            await page.wait_for_function(
                """() => {
                    const spans = Array.from(document.querySelectorAll("span.font-gotham-book"));
                    const nums = spans
                      .map(s => (s.textContent || "").trim())
                      .map(t => t.match(/\\d+[.,]\\d{3,4}/)?.[0])
                      .filter(Boolean)
                      .map(v => parseFloat(v.replace(",", ".")))
                      .filter(n => !Number.isNaN(n) && n > 0);

                    // Queremos mínimo 2 tasas
                    return nums.length >= 2;
                }""",
                timeout=25000
            )

            spans = await page.locator("span.font-gotham-book").all_text_contents()

            # Extraer números en orden de aparición
            rates = []
            for s in spans:
                num = _extract_rate(s)
                if num:
                    val = normalize_rate(num)
                    if val is not None:
                        rates.append(val)

            # A veces aparecen otros números, nos quedamos con los primeros 2
            if len(rates) < 2:
                raise Exception(f"No se encontraron suficientes tasas válidas. Capturado: {spans[:10]}")

            compra, venta = rates[0], rates[1]

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
            "compra": None,
            "venta": None,
            "error": f"No se pudo scrapear: {e}"
        }
    finally:
        if browser:
            await browser.close()
