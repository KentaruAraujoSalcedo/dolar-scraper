import httpx
from scrapers.utils import normalize_rate

async def scrap_defiperu():
    casa = "DefiPeru"
    url = "https://defiperu.com/change/FIAT"
    endpoint = "https://defi.frojo.dev/api/ExchangeRates/currencyType"
    params = {"currencyType": "FIAT"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://defiperu.com/",
        "Origin": "https://defiperu.com",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint, params=params)
            r.raise_for_status()
            data = r.json()

        if not isinstance(data, list) or not data:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": f"Respuesta inesperada: {type(data).__name__}",
            }

        # El endpoint devuelve una lista; escogemos la de PEN->USD
        item = next(
            (x for x in data if x.get("fromCurrency") == "PEN" and x.get("toCurrency") == "USD"),
            data[0],
        )

        compra_raw = item.get("purchase")
        venta_raw = item.get("sale")

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
