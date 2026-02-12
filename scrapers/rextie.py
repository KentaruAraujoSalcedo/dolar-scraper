import httpx
from scrapers.utils import normalize_rate

async def scrap_rextie():
    casa = "Rextie"
    url = "https://www.rextie.com/"
    endpoint = "https://app.rextie.com/api/graphql/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.rextie.com",
        "Referer": "https://www.rextie.com/",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
    }

    # Query mínimo para tasas actuales (según lo que vimos en tu preview)
    payload = {
        "query": """
            query CurrentFxRates {
              currentFxRates {
                source
                ask
                bid
              }
            }
        """,
        "variables": {}
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.post(endpoint, json=payload)
            r.raise_for_status()
            data = r.json()

        rates = (data or {}).get("data", {}).get("currentFxRates", [])
        if not isinstance(rates, list) or not rates:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "Respuesta GraphQL inesperada (sin currentFxRates).",
            }

        # Preferimos la fuente REXTIE
        rextie = next((x for x in rates if str(x.get("source", "")).upper() == "REXTIE"), None)
        if not rextie:
            # fallback: si no aparece, toma el primero
            rextie = rates[0]

        compra_raw = rextie.get("bid")  # compra
        venta_raw  = rextie.get("ask")  # venta

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
