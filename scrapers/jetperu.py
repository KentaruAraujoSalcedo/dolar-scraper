import re
import time
import json
import base64
import httpx
from scrapers.utils import normalize_rate

_JETPERU_TOKEN = {"value": None, "exp": 0}

def _jwt_exp(jwt: str) -> int:
    try:
        parts = jwt.split(".")
        if len(parts) < 2:
            return 0
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
        return int(payload.get("exp", 0))
    except Exception:
        return 0

async def _get_jetperu_token(client: httpx.AsyncClient) -> str:
    now = int(time.time())
    if _JETPERU_TOKEN["value"] and (_JETPERU_TOKEN["exp"] - 60) > now:
        return _JETPERU_TOKEN["value"]

    ajax_url = "https://jetperu.com.pe/wp-admin/admin-ajax.php"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://jetperu.com.pe/cambiar-dinero/",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    r = await client.post(ajax_url, headers=headers, data={"action": "tc_token"})
    r.raise_for_status()

    j = r.json()
    if not isinstance(j, dict) or not j.get("success") or not j.get("data"):
        snippet = (r.text or "")[:300].replace("\n", " ")
        raise RuntimeError(f"Respuesta inesperada de tc_token. Snippet: {snippet}")

    token = j["data"]
    exp = _jwt_exp(token)

    _JETPERU_TOKEN["value"] = token
    _JETPERU_TOKEN["exp"] = exp if exp else (int(time.time()) + 10 * 60)
    return token


def _extract_widget_rates_if_present(html: str):
    """
    OJO: normalmente estos spans vienen VACÍOS y se llenan con JS.
    Solo sirve si alguna vez el HTML ya trae números (poco común).
    """
    h = html or ""

    buy = re.search(
        r'<span[^>]*\bid\s*=\s*[\'"]buyRate[\'"][^>]*>\s*([0-9]+[.,][0-9]{3,4})\s*</span>',
        h, re.I
    )
    sell = re.search(
        r'<span[^>]*\bid\s*=\s*[\'"]sellRate[\'"][^>]*>\s*([0-9]+[.,][0-9]{3,4})\s*</span>',
        h, re.I
    )

    buy_raw = buy.group(1) if buy else None
    sell_raw = sell.group(1) if sell else None

    compra = normalize_rate(buy_raw) if buy_raw else None
    venta = normalize_rate(sell_raw) if sell_raw else None
    return compra, venta


def _pick_item(items: list, moneda_id: str):
    return next((it for it in items if isinstance(it, dict) and it.get("monedaDestinoId") == moneda_id), None)


async def scrap_jetperu():
    casa = "JetPeru"
    url = "https://jetperu.com.pe/cambiar-dinero/"

    endpoint = "https://apitc.jetperu.com.pe:5002/api/WebTipoCambio"
    params = {"monedaOrigenId": "PEN"}

    timeout = httpx.Timeout(20.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # 1) Intento HTML (opcional; casi siempre vacío)
            page = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            page.raise_for_status()

            compra_html, venta_html = _extract_widget_rates_if_present(page.text)
            if compra_html is not None and venta_html is not None:
                return {
                    "casa": casa,
                    "url": url,
                    "compra": compra_html,
                    "venta": venta_html,
                    "estado": "abierto",
                    "source": "html_widget_buyRate_sellRate",
                }

            # 2) ✅ Fuente real: API + token
            token = await _get_jetperu_token(client)

            headers_api = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Referer": "https://jetperu.com.pe/",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Authorization": f"Bearer {token}",
            }

            r = await client.get(endpoint, params=params, headers=headers_api)
            r.raise_for_status()
            data = r.json()

        if not isinstance(data, dict) or not data.get("exito"):
            return {
                "casa": casa, "url": url,
                "compra": None, "venta": None,
                "estado": "error",
                "source": "api_WebTipoCambio",
                "error": "API exito != true",
            }

        items = data.get("dato") or []
        if not isinstance(items, list) or not items:
            return {
                "casa": casa, "url": url,
                "compra": None, "venta": None,
                "estado": "error",
                "source": "api_WebTipoCambio",
                "error": "API dato vacío",
            }

        # ✅ Primero USDO (online = lo que muestra el widget)
        it = _pick_item(items, "USDO") or _pick_item(items, "USD")
        if not it:
            return {
                "casa": casa, "url": url,
                "compra": None, "venta": None,
                "estado": "error",
                "source": "api_WebTipoCambio",
                "error": "No USDO ni USD en API",
            }

        compra = normalize_rate(str(it.get("tipoCompra"))) if it.get("tipoCompra") is not None else None
        venta  = normalize_rate(str(it.get("tipoVenta"))) if it.get("tipoVenta") is not None else None

        return {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": "abierto" if (compra is not None and venta is not None) else "error",
            "source": f"api_WebTipoCambio_{it.get('monedaDestinoId')}",
        }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "source": "missing",
            "error": f"No se pudo scrapear: {e}",
        }
