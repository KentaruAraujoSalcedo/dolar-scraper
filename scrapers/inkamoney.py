import re
import httpx
from scrapers.utils import normalize_rate

CSRF_RE = re.compile(r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']', re.I)

async def scrap_inkamoney():
    casa = "inkamoney"
    url = "https://inkamoney.com/"
    endpoint = "https://inkamoney.com/convert"

    headers_get = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": url,
    }

    timeout = httpx.Timeout(20.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # 1) GET home para extraer CSRF + cookies
            r1 = await client.get(url, headers=headers_get)
            r1.raise_for_status()

            html = r1.text or ""
            m = CSRF_RE.search(html)
            if not m:
                snippet = html[:800].replace("\n", " ").replace("\r", " ")
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error": f"No se encontró CSRF token. Snippet: {snippet}",
                }

            csrf = m.group(1)

            # 2) POST /convert como el navegador (AJAX + CSRF)
            headers_post = {
                "User-Agent": headers_get["User-Agent"],
                "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
                "Accept": "application/json, text/plain, */*",
                "Referer": url,
                "Origin": "https://inkamoney.com",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-TOKEN": csrf,
                "Content-Type": "application/json;charset=UTF-8",
            }

            payload = {"amount": 1000, "currency": "PEN", "type": "buy", "credits": 0}

            r2 = await client.post(endpoint, headers=headers_post, json=payload)
            r2.raise_for_status()
            data = r2.json()

        if not isinstance(data, dict):
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": f"JSON inesperado (type={type(data)}).",
            }

        # OJO: según tu respuesta, estos campos existen
        compra_raw = data.get("fxBaseBuy")
        venta_raw  = data.get("fxBaseSale")

        compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
        venta  = normalize_rate(str(venta_raw)) if venta_raw is not None else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        return {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": "cerrado" if cerrado else "abierto",
        }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
