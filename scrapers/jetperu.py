import httpx
from scrapers.utils import normalize_rate

async def scrap_jetperu():
    casa = "JetPeru"
    url = "https://jetperu.com.pe/cambiar-dinero/"
    endpoint = "https://apitc.jetperu.com.pe:5002/api/WebTipoCambio"
    params = {"monedaOrigenId": "PEN"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
        "Origin": "https://jetperu.com.pe",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint, params=params)
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
        venta_raw = usd.get("tipoVenta")

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
