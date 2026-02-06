# scrapers/defiperu.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")

def _num(txt: str):
    if not txt:
        return None
    m = NUM_RE.search(txt.replace(" ", ""))
    return m.group(0) if m else None

async def scrap_defiperu():
    url = "https://defiperu.com/change/FIAT"
    casa = "DefiPeru"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Esperar a que existan 2 valores de rate
            await page.wait_for_function(
                """() => {
                    const vals = Array.from(document.querySelectorAll('span.rate-value'))
                      .map(e => (e.textContent||'').trim())
                      .filter(t => /\\d/.test(t));
                    const types = Array.from(document.querySelectorAll('span.rate-type'))
                      .map(e => (e.textContent||'').trim().toLowerCase());
                    return vals.length >= 2 && types.includes('compra') && types.includes('venta');
                }""",
                timeout=25000
            )

            compra = venta = None

            # Cada bloque tiene rate-value + rate-type. Tomamos el contenedor cercano.
            types = page.locator("span.rate-type")
            for i in range(await types.count()):
                t = (await types.nth(i).text_content() or "").strip().lower()
                container = types.nth(i).locator("xpath=ancestor::*[self::div][1]")
                # fallback: sube 2 niveles si el 1 no contiene rate-value
                val_loc = container.locator("span.rate-value").first
                if await val_loc.count() == 0:
                    container = types.nth(i).locator("xpath=ancestor::*[self::div][2]")
                    val_loc = container.locator("span.rate-value").first

                val_txt = (await val_loc.text_content() or "").strip()
                n = _num(val_txt)
                n = normalize_rate(n.replace(",", ".")) if n else None
                if n is None:
                    continue

                if t == "compra":
                    compra = n
                elif t == "venta":
                    venta = n

            if compra is None or venta is None:
                raise Exception(f"No se pudieron identificar compra/venta (compra={compra}, venta={venta})")

            return {"casa": casa, "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": casa, "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}

    finally:
        if browser:
            await browser.close()
