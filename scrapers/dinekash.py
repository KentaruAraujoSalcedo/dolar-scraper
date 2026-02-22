import httpx
from scrapers.utils import normalize_rate

async def scrap_dinekash():
    casa = "dinekash"
    url = "https://dinekash.pe/"

    endpoint_base = "https://api.dinekash.pe/cotizacion/buscar"
    pair_a = "USDPEN"
    pair_b = "PENUSD"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Origin": "https://dinekash.pe",
        "Referer": "https://dinekash.pe/",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r1 = await client.get(f"{endpoint_base}/{pair_a}")
            r2 = await client.get(f"{endpoint_base}/{pair_b}")
            r1.raise_for_status()
            r2.raise_for_status()

            j1 = r1.json()
            j2 = r2.json()

        def get_quote(j):
            if not isinstance(j, dict) or not j.get("ok"):
                return None
            arr = j.get("cotizacion") or []
            if not arr or not isinstance(arr, list):
                return None
            val = arr[0].get("cotizacion")
            return float(val) if val is not None else None

        q_usdpen = get_quote(j1)  # 3.353 (según tu preview)
        q_penusd = get_quote(j2)  # 3.358 (según tu preview)

        quotes = [q for q in (q_usdpen, q_penusd) if isinstance(q, (int, float))]
        if len(quotes) < 2:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "No se pudo obtener ambas cotizaciones (USDPEN y PENUSD).",
            }

        compra = normalize_rate(str(min(quotes)))
        venta  = normalize_rate(str(max(quotes)))

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
