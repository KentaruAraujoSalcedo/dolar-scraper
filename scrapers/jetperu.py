import time
import json
import base64
import httpx
from scrapers.utils import normalize_rate

# Cache simple en memoria (sirve perfecto si tu run_scrapers corre en un solo proceso)
_JETPERU_TOKEN = {"value": None, "exp": 0}

def _jwt_exp(jwt: str) -> int:
    """Devuelve exp (epoch seconds) del JWT. Si falla, 0."""
    try:
        parts = jwt.split(".")
        if len(parts) < 2:
            return 0
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)  # padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
        return int(payload.get("exp", 0))
    except Exception:
        return 0

async def _get_jetperu_token(client: httpx.AsyncClient) -> str:
    now = int(time.time())
    # refresca 60s antes de expirar
    if _JETPERU_TOKEN["value"] and (_JETPERU_TOKEN["exp"] - 60) > now:
        return _JETPERU_TOKEN["value"]

    ajax_url = "https://jetperu.com.pe/wp-admin/admin-ajax.php"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://jetperu.com.pe/cambiar-dinero/",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    # lo que capturaste:
    data = {"action": "tc_token"}

    r = await client.post(ajax_url, headers=headers, data=data)
    r.raise_for_status()

    j = r.json()
    if not isinstance(j, dict) or not j.get("success") or not j.get("data"):
        snippet = (r.text or "")[:300].replace("\n", " ")
        raise RuntimeError(f"Respuesta inesperada de tc_token. Snippet: {snippet}")

    token = j["data"]
    exp = _jwt_exp(token)

    _JETPERU_TOKEN["value"] = token
    _JETPERU_TOKEN["exp"] = exp if exp else (int(time.time()) + 10 * 60)  # fallback 10 min

    return token

async def scrap_jetperu():
    casa = "JetPeru"
    url = "https://jetperu.com.pe/cambiar-dinero/"
    endpoint = "https://apitc.jetperu.com.pe:5002/api/WebTipoCambio"
    params = {"monedaOrigenId": "PEN"}

    timeout = httpx.Timeout(20.0, connect=10.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            token = await _get_jetperu_token(client)

            headers_api = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Referer": "https://jetperu.com.pe/",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Authorization": f"Bearer {token}",
            }

            r = await client.get(endpoint, params=params, headers=headers_api)
            r.raise_for_status()
            data = r.json()

        if not isinstance(data, dict) or not data.get("exito"):
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "Respuesta inesperada del API (exito != true).",
            }

        items = data.get("dato") or []
        if not isinstance(items, list) or not items:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "Respuesta inesperada del API (dato vacío).",
            }

        usd = next((it for it in items if it.get("monedaDestinoId") == "USD"), None)
        if not usd:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "No se encontró registro USD en la respuesta.",
            }

        compra_raw = usd.get("tipoCompra")
        venta_raw  = usd.get("tipoVenta")

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
