# scrapers/cambiomundial.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")

def _extract_number(txt: str):
    if not txt:
        return None
    m = NUM_RE.search(txt)
    return m.group(0) if m else None

async def scrap_cambiomundial():
    url = "https://www.cambiomundial.com/"
    casa = "CambioMundial"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            context = await browser.new_context(
                locale="es-PE",
                timezone_id="America/Lima",
                viewport={"width": 1280, "height": 720},
            )
            page = await context.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # 1) Fuente más estable: inputs hidden con value
            await page.wait_for_function(
                """() => {
                    const c = document.querySelector('#valorcompra')?.getAttribute('value') || '';
                    const v = document.querySelector('#valorventa')?.getAttribute('value') || '';
                    return /\\d/.test(c) && /\\d/.test(v);
                }""",
                timeout=20000
            )

            compra_val = await page.get_attribute("#valorcompra", "value")
            venta_val  = await page.get_attribute("#valorventa", "value")

            compra_num = _extract_number(compra_val or "")
            venta_num  = _extract_number(venta_val or "")

            compra = normalize_rate(compra_num) if compra_num else None
            venta  = normalize_rate(venta_num)  if venta_num  else None

            # 2) Fallback: labels (por si cambian los inputs)
            if compra is None or venta is None:
                await page.locator("#lblvalorcompra").first.wait_for(state="attached", timeout=15000)
                await page.locator("#lblvalorventa").first.wait_for(state="attached", timeout=15000)

                compra_txt = (await page.locator("#lblvalorcompra").first.text_content() or "").strip()
                venta_txt  = (await page.locator("#lblvalorventa").first.text_content() or "").strip()

                compra_num = _extract_number(compra_txt)
                venta_num  = _extract_number(venta_txt)

                compra = normalize_rate(compra_num) if compra_num else compra
                venta  = normalize_rate(venta_num)  if venta_num  else venta

            if compra is None or venta is None:
                raise Exception(f"No se pudieron leer tasas (valorcompra={compra_val}, valorventa={venta_val})")

            return {"casa": casa, "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": casa, "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}

    finally:
        if browser:
            await browser.close()
