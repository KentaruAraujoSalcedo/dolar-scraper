# scrapers/roblex.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")

def _extract_number(txt: str):
    if not txt:
        return None
    m = NUM_RE.search(txt)
    return m.group(1) if m else None

async def scrap_roblex():
    url = "https://roblex.pe/"
    casa = "Roblex"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Esperar a que aparezcan labels con Compra y Venta
            await page.wait_for_function(
                """() => {
                    const labels = Array.from(document.querySelectorAll('label'))
                      .map(e => (e.textContent||'').toLowerCase());
                    return labels.some(t => t.includes('compra')) && labels.some(t => t.includes('venta'));
                }""",
                timeout=25000
            )

            compra_label = page.locator("label", has_text=re.compile(r"Compra", re.I)).first
            venta_label  = page.locator("label", has_text=re.compile(r"Venta", re.I)).first

            await compra_label.wait_for(state="attached", timeout=25000)
            await venta_label.wait_for(state="attached", timeout=25000)

            compra_raw = (await compra_label.text_content() or "").strip()
            venta_raw  = (await venta_label.text_content()  or "").strip()

            compra_txt = _extract_number(compra_raw)
            venta_txt  = _extract_number(venta_raw)

            compra = normalize_rate(compra_txt.replace(",", ".")) if compra_txt else None
            venta  = normalize_rate(venta_txt.replace(",", "."))  if venta_txt  else None

            if compra is None or venta is None:
                raise Exception(f"No se pudieron leer tasas (compra_raw={compra_raw!r}, venta_raw={venta_raw!r})")

            return {"casa": casa, "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": casa, "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}

    finally:
        if browser:
            await browser.close()
