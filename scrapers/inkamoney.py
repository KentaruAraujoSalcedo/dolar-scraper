import re
import asyncio
from playwright.async_api import async_playwright

NUM_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)")

def _to_float(text: str) -> float:
    # soporta "S/ 3.3560" o "3,3560"
    m = NUM_RE.search(text.replace("S/", "").replace(" ", "").strip())
    if not m:
        raise ValueError(f"No pude parsear número de: {text!r}")
    return float(m.group(1).replace(",", "."))

async def _try_once(page) -> dict:
    url = "https://inkamoney.com/"
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)

    # Locators por texto + span interno (no depende del "S/" en el bloque)
    compra_span = page.locator(".prices .h6", has_text=re.compile(r"COMPRA", re.I)).locator("span")
    vende_span  = page.locator(".prices .h6", has_text=re.compile(r"VENDE|VENTA", re.I)).locator("span")

    # Espera a que existan (por si el bloque se renderiza tarde)
    await compra_span.first.wait_for(state="visible", timeout=20000)
    await vende_span.first.wait_for(state="visible", timeout=20000)

    # Espera a que AMBOS tengan número
    async def _wait_number(locator, timeout=20000):
        await locator.first.wait_for(state="visible", timeout=timeout)
        await page.wait_for_function(
            """(el) => !!el && /\\d/.test(el.innerText)""",
            arg=await locator.first.element_handle(),
            timeout=timeout
        )
        return (await locator.first.text_content()) or ""

    compra_txt = await _wait_number(compra_span, timeout=20000)
    vende_txt  = await _wait_number(vende_span, timeout=20000)

    compra = _to_float(compra_txt)
    venta  = _to_float(vende_txt)

    return {"casa": "InkaMoney", "url": url, "compra": compra, "venta": venta}

async def scrap_inkamoney():
    url = "https://inkamoney.com/"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Retry simple (por intermitencia)
            last_err = None
            for attempt in range(3):
                try:
                    res = await _try_once(page)
                    await browser.close()
                    return res
                except Exception as e:
                    last_err = e
                    # pequeño backoff
                    await asyncio.sleep(0.6 * (attempt + 1))

            await browser.close()
            raise last_err

    except Exception as e:
        return {"casa": "InkaMoney", "url": url, "error": f"No se pudo scrapear: {e}"}
