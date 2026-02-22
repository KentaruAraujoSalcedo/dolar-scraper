import httpx
from scrapers.utils import normalize_rate

async def scrap_megamoney():
    casa = "megamoney"
    url = "https://megamoney.pe/"
    endpoint = "https://api.megamoney.pe/api/v1/divisas"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://megamoney.pe",
        "Referer": "https://megamoney.pe/",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint)
            r.raise_for_status()
            payload = r.json()

        # Esperado: {"code":"00","data":[...]}
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": f"Respuesta inesperada (sin data[]): {type(payload).__name__}",
            }

        usd = next((x for x in data if str(x.get("code", "")).upper() == "USD"), None)
        if not usd:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "No se encontró USD en data[]",
            }

        compra_raw = usd.get("buyValue")
        venta_raw  = usd.get("sellValue")

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
