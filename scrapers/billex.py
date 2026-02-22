import httpx
from scrapers.utils import normalize_rate

async def scrap_billex():
    casa = "billex"
    url = "https://www.billex.pe/"
    endpoint = "https://apiprod.billex.pe/api/res/tcambio"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Origin": "https://www.billex.pe",
        "Referer": "https://www.billex.pe/",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20) as client:
            r = await client.get(endpoint)
            r.raise_for_status()
            data = r.json()

        # Según tu preview: {"tc_venta":3.337,"tc_compra":3.37}
        compra = normalize_rate(str(data.get("tc_compra"))) if data.get("tc_compra") is not None else None
        venta  = normalize_rate(str(data.get("tc_venta")))  if data.get("tc_venta")  is not None else None

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
