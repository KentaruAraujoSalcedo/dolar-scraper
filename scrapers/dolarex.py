import asyncio
import httpx
from scrapers.utils import normalize_rate

async def scrap_dolarex():
    casa = "dolarex"
    url = "https://dolarex.pe/"

    endpoints = [
        "https://api.dolarex.pe/cotizacion/buscar/USDPEN",
        "https://api.dolarex.pe/cotizacion/buscar/PENUSD",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Origin": "https://dolarex.pe",
        "Referer": "https://dolarex.pe/",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
            # pide ambos en paralelo
            r1, r2 = await asyncio.gather(
                client.get(endpoints[0]),
                client.get(endpoints[1]),
            )

        r1.raise_for_status()
        r2.raise_for_status()

        j1 = r1.json()
        j2 = r2.json()

        def extract_rate(j):
            # {"ok":true,"cotizacion":[{"cotizacion":"3.357"}]}
            arr = j.get("cotizacion") or []
            if not arr:
                return None
            val = arr[0].get("cotizacion")
            return float(val) if val is not None else None

        v1 = extract_rate(j1)
        v2 = extract_rate(j2)

        vals = [v for v in (v1, v2) if isinstance(v, (int, float))]
        if len(vals) < 2:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": f"Respuesta inesperada (v1={v1}, v2={v2})",
            }

        compra = normalize_rate(str(min(vals)))
        venta  = normalize_rate(str(max(vals)))

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
