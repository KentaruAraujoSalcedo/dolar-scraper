# scrapers/mercadocambiario.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")

def _num(txt: str):
    if not txt:
        return None
    m = NUM_RE.search(txt)
    return m.group(0) if m else None

async def scrap_mercadocambiario():
    url = "https://mercadocambiario.pe/"
    casa = "MercadoCambiario"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Esperar a que existan AL MENOS 2 montos con números
            await page.wait_for_function(
                """() => {
                    const amts = [...document.querySelectorAll('span.amount')]
                        .map(x => (x.innerText||'').trim())
                        .filter(t => /\\d/.test(t));
                    return amts.length >= 2;
                }""",
                timeout=30000
            )

            spans = page.locator("span.amount")
            textos = []

            for i in range(await spans.count()):
                t = (await spans.nth(i).text_content() or "").strip()
                if _num(t):
                    textos.append(t)

            if len(textos) < 2:
                raise Exception(f"No se encontraron 2 montos válidos: {textos}")

            compra_txt = _num(textos[0].replace(",", "."))
            venta_txt  = _num(textos[1].replace(",", "."))

            compra = normalize_rate(compra_txt)
            venta  = normalize_rate(venta_txt)

            if compra is None or venta is None:
                raise Exception(f"Montos inválidos compra={compra_txt}, venta={venta_txt}")

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
