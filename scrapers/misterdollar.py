# scrapers/misterdollar.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _pick(txt: str):
    if not txt:
        return None
    m = RATE_RE.search(txt)
    return m.group(0) if m else None

async def scrap_misterdollar():
    url = "https://misterdollar.pe/"
    casa = "MisterDollar"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            compra_loc = page.locator(".views-field-field-t-c-compra .field-content span.cant").first
            venta_loc  = page.locator(".views-field-field-t-c-venta  .field-content span.cant").first

            await compra_loc.wait_for(state="attached", timeout=20000)
            await venta_loc.wait_for(state="attached", timeout=20000)

            # Esperar formato tasa real
            await page.wait_for_function(
                """() => {
                    const c = document.querySelector('.views-field-field-t-c-compra .field-content span.cant')?.textContent || '';
                    const v = document.querySelector('.views-field-field-t-c-venta  .field-content span.cant')?.textContent || '';
                    return /\\b\\d[\\.,]\\d{3,4}\\b/.test(c) && /\\b\\d[\\.,]\\d{3,4}\\b/.test(v);
                }""",
                timeout=20000
            )

            compra_raw = (await compra_loc.text_content() or "").strip()
            venta_raw  = (await venta_loc.text_content()  or "").strip()

            compra_txt = _pick(compra_raw)
            venta_txt  = _pick(venta_raw)

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
