import os
import httpx
from scrapers.utils import normalize_rate

async def scrap_cambix():
    casa = "cambix"
    url = "https://cambix.com.pe/"
    endpoint = "https://apibcprod01.azure-api.net/cambix/v2/exchange-rates/exchange-rate"
    params = {"typeCode": "TC", "documentNumber": "null"}

    ocp_key = os.getenv("CAMBIX_OCP_KEY")
    if not ocp_key:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": "Falta la variable de entorno CAMBIX_OCP_KEY (ocp-apim-subscription-key).",
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://cambix.com.pe/",
        "Origin": "https://cambix.com.pe",
        "ocp-apim-subscription-key": ocp_key,
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint, params=params)
            r.raise_for_status()
            data = r.json()

        compra_raw = data.get("purchase") if isinstance(data, dict) else None
        venta_raw  = data.get("sale") if isinstance(data, dict) else None

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
