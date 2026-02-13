import re
import urllib.parse
import httpx
from scrapers.utils import normalize_rate

META_CSRF_RE = re.compile(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', re.I)

async def scrap_chaskidolar():
    casa = "ChaskiDolar"
    url = "https://chaskidolar.com/"
    endpoint = "https://chaskidolar.com/convert"

    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": url,
        "Origin": "https://chaskidolar.com",
    }

    timeout = httpx.Timeout(20.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # 1) GET home para cookies + meta csrf
            r1 = await client.get(url, headers={**headers_base, "Accept": "text/html,application/xhtml+xml"})
            r1.raise_for_status()

            html = r1.text or ""
            m = META_CSRF_RE.search(html)
            meta_csrf = m.group(1) if m else None

            xsrf_cookie = client.cookies.get("XSRF-TOKEN")
            xsrf_decoded = urllib.parse.unquote(xsrf_cookie) if xsrf_cookie else None

            if not meta_csrf and not xsrf_decoded:
                snippet = html[:600].replace("\n", " ").replace("\r", " ")
                return {
                    "casa": casa, "url": url, "compra": None, "venta": None, "estado": "error",
                    "error": f"No pude obtener CSRF (meta/cookie). Snippet: {snippet}",
                }

            headers_post = {
                **headers_base,
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json",
            }
            if meta_csrf:
                headers_post["X-CSRF-TOKEN"] = meta_csrf
            if xsrf_decoded:
                headers_post["X-XSRF-TOKEN"] = xsrf_decoded

            # 2) Payload definitivo (descubierto)
            payload = {
                "amount": 1000,
                "currency": "USD",
                "type": "buy",
                "credits": 0,
            }

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

        buy_raw = data.get("fxBaseBuy")
        sale_raw = data.get("fxBaseSale")

        buy = normalize_rate(str(buy_raw)) if buy_raw is not None else None
        sale = normalize_rate(str(sale_raw)) if sale_raw is not None else None

        # Normalizamos para tu comparador: compra < venta
        if buy is None or sale is None:
            compra = venta = None
        else:
            compra = min(buy, sale)
            venta = max(buy, sale)

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
