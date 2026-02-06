# scrapers/cambioselgordito.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{2,4}\b")  # compra puede venir 3.36

def _to_rate(s: str):
    if not s:
        return None
    m = RATE_RE.search(s)
    if not m:
        return None
    return normalize_rate(m.group(0).replace(",", "."))

async def scrap_cambioselgordito():
    url = "https://cambioselgordito.com/"
    casa = "CambiosElGordito"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Encuentra el bloque que contiene "Compra" y "Venta"
            bloque = page.get_by_text(re.compile(r"Compra.*Venta|Venta.*Compra", re.I)).first
            await bloque.wait_for(timeout=25000)

            # En ese bloque, hay 2 <b>: [0]=compra, [1]=venta
            bs = bloque.locator("b")
            await bs.first.wait_for(timeout=25000)

            # espera a que existan 2
            if await bs.count() < 2:
                # fallback: busca el contenedor padre y reintenta
                bloque = bloque.locator("xpath=ancestor::*[self::p or self::div][1]")
                bs = bloque.locator("b")

            if await bs.count() < 2:
                raise Exception("No encontré 2 valores <b> para Compra/Venta")

            compra_raw = (await bs.nth(0).text_content() or "").strip()
            venta_raw  = (await bs.nth(1).text_content() or "").strip()

            compra = _to_rate(compra_raw)
            venta  = _to_rate(venta_raw)

            if compra is None or venta is None:
                raise Exception(f"No se pudieron parsear tasas (compra_raw={compra_raw!r}, venta_raw={venta_raw!r})")

            return {"casa": casa, "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": casa, "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}

    finally:
        if browser:
            await browser.close()
