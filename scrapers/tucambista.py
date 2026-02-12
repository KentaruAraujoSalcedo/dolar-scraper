import os
import httpx
from scrapers.utils import normalize_rate

async def scrap_tucambista():
    casa = "TuCambista"
    url = "https://tucambista.pe/"
    endpoint_rates = "https://apim.tucambista.pe/api/rates"
    endpoint_quote = "https://apim.tucambista.pe/api/transaction/quote"

    # Ponlo en .env o en tus secrets:
    # TUCAMBISTA_OCP_KEY="e4b6947d...;product=tucambista-production"
    ocp_key = os.getenv("TUCAMBISTA_OCP_KEY")

    if not ocp_key:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": "Falta la variable de entorno TUCAMBISTA_OCP_KEY (ocp-apim-subscription-key).",
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://tucambista.pe/",
        "Origin": "https://tucambista.pe",
        "ocp-apim-subscription-key": ocp_key,
    }

    timeout = httpx.Timeout(20.0, connect=10.0)

    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
            # 1) Intento rápido: /api/rates
            r = await client.get(endpoint_rates)
            r.raise_for_status()
            data = r.json()

            # /api/rates a veces devuelve dict con bid/offer, a veces lista (según tu debug)
            if isinstance(data, dict) and ("bidRate" in data or "offerRate" in data):
                compra_raw = data.get("bidRate")
                venta_raw = data.get("offerRate")
            else:
                # 2) Fallback sólido: /api/transaction/quote (siempre trae bid/offer)
                payload = {
                    "amount": 500,
                    "buyOrSell": "BUY",
                    "ccy": "USD",
                    "totalCreditsToUse": 0,
                    "cancelPromotionCode": "",
                    "promotionCode": "",
                    "utmSource": "google",
                    "utmMedium": "organic",
                    "utmCampaign": "",
                    "utmContent": "tucambista",
                }
                r2 = await client.post(endpoint_quote, json=payload)
                r2.raise_for_status()
                q = r2.json()

                compra_raw = q.get("bidRate")
                venta_raw = q.get("offerRate")

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
