import httpx
from scrapers.utils import normalize_rate

async def scrap_safex():
    casa = "Safex"
    url = "https://www.safex.pe/"
    endpoint = "https://www.safex.pe/cotizacion/cotizacion.php"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.safex.pe/",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint)
            r.raise_for_status()

            # A veces viene como text/html aunque sea JSON
            try:
                payload = r.json()
            except Exception:
                payload = httpx.Response(200, text=r.text).json()  # fallback
                # (si esto no te gusta, lo cambiamos por json.loads)

        if not isinstance(payload, dict) or payload.get("response") != "success":
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": f"Respuesta inesperada: {payload!r}",
            }

        data = payload.get("data") or {}
        compra_raw = data.get("precCompra")
        venta_raw  = data.get("precVenta")

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
