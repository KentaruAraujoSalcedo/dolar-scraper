import httpx
from scrapers.utils import normalize_rate

async def scrap_srcambio():
    casa = "SRcambio"
    url = "https://srcambio.pe/"
    endpoint = "https://srcambio.pseperu.pro/api/exchange-rates/last-exchange-rate"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://srcambio.pe",
        "Referer": "https://srcambio.pe/",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint)
            r.raise_for_status()
            data = r.json()

        compra_raw = data.get("priceCompra")
        venta_raw  = data.get("priceVenta")

        compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
        venta  = normalize_rate(str(venta_raw)) if venta_raw is not None else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        out = {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": "cerrado" if cerrado else "abierto",
        }

        # opcional: guardar fecha de registro si te sirve para tu histórico
        if isinstance(data, dict) and data.get("dateRegister"):
            out["timestamp"] = data["dateRegister"]

        return out

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
