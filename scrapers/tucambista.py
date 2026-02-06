# scrapers/tucambista.py
import re
import json
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _find_rates_in_obj(obj):
    """Busca strings tipo 3.355 / 3,3550 dentro de un JSON (recursivo)."""
    found = []

    def walk(x):
        if x is None:
            return
        if isinstance(x, (int, float)):
            # no tomamos ints sueltos, pero floats podrían servir
            s = str(x)
            if RATE_RE.search(s):
                found.append(s)
            return
        if isinstance(x, str):
            m = RATE_RE.search(x)
            if m:
                found.append(m.group(0))
            return
        if isinstance(x, list):
            for it in x:
                walk(it)
            return
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
            return

    walk(obj)
    return found

async def scrap_tucambista():
    url = "https://tucambista.pe/"
    casa = "TuCambista"
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

            got = {"compra": None, "venta": None}

            async def handle_response(resp):
                try:
                    ct = (resp.headers.get("content-type") or "").lower()
                    if "application/json" not in ct:
                        return
                    # Evita bajar JSON gigantes irrelevantes
                    if resp.status != 200:
                        return

                    data = await resp.json()
                    rates = _find_rates_in_obj(data)

                    # Si encontramos 2+ números tipo 3.xxx, probamos usarlos
                    if len(rates) >= 2 and (got["compra"] is None or got["venta"] is None):
                        # normalizamos y tomamos los 2 primeros distintos
                        nums = []
                        for r in rates:
                            n = normalize_rate(r.replace(",", "."))
                            if n and n not in nums:
                                nums.append(n)
                            if len(nums) >= 2:
                                break
                        if len(nums) >= 2:
                            got["compra"], got["venta"] = nums[0], nums[1]
                except Exception:
                    pass

            page.on("response", handle_response)

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # espera un poco a que lleguen XHRs
            await page.wait_for_timeout(4000)

            if got["compra"] is None or got["venta"] is None:
                # fallback: intenta leer del HTML pero SOLO si no es 0.000
                compra_txt = (await page.locator("button:has-text('Compra') span").all_text_contents())
                venta_txt  = (await page.locator("button:has-text('Venta') span").all_text_contents())
                # busca algo que no sea 0.000
                def pick(arr):
                    for t in arr:
                        t = (t or "").strip()
                        if t == "0.000":
                            continue
                        if RATE_RE.search(t):
                            return normalize_rate(t.replace(",", "."))
                    return None

                got["compra"] = got["compra"] or pick(compra_txt)
                got["venta"]  = got["venta"]  or pick(venta_txt)

            if got["compra"] is None or got["venta"] is None:
                raise Exception("La web solo devolvió 0.000 (no cargó tasas). Probable bloqueo/API no respondió en headless.")

            return {"casa": casa, "url": url, "compra": got["compra"], "venta": got["venta"]}

    except Exception as e:
        return {"casa": casa, "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}

    finally:
        if browser:
            await browser.close()
