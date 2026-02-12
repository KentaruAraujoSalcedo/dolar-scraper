import re
import httpx
from scrapers.utils import normalize_rate

TOKEN_RE = re.compile(r'__RequestVerificationToken[^>]*value=["\']([^"\']+)["\']', re.I)

async def scrap_westernunion():
    casa = "WesternUnion"
    url = "https://www.westernunionperu.pe/cambiodemoneda"
    endpoint = "https://www.westernunionperu.pe/cambiodemoneda/Operation/PostTipoCambio"

    headers_get = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": url,
    }

    headers_post = {
        "User-Agent": headers_get["User-Agent"],
        "Accept-Language": "es-PE",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": url,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    timeout = httpx.Timeout(20.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r1 = await client.get(url, headers=headers_get)
            r1.raise_for_status()

            html = r1.text or ""
            m = TOKEN_RE.search(html)
            if not m:
                snippet = html[:800].replace("\n", " ").replace("\r", " ")
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error": f"No se encontró __RequestVerificationToken. Snippet: {snippet}",
                }

            token = m.group(1)

            form = {
                "monto": "1000",
                "moneda": "2",
                "tipo": "1",
                "__RequestVerificationToken": token,
                "ERequestServicesGeneral[Recaptcha]": "",
            }

            r2 = await client.post(endpoint, headers=headers_post, data=form)
            r2.raise_for_status()

            data = r2.json() if r2.content else {}
            if not isinstance(data, dict):
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error": f"JSON inesperado (type={type(data)}).",
                }

            compra_raw = data.get("DT_Compra") or data.get("TC_Compra") or data.get("TCB_Compra")
            venta_raw  = data.get("DT_Venta")  or data.get("TC_Venta")  or data.get("TCB_Venta")

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
