import httpx
from scrapers.utils import normalize_rate

API = "https://api.global66.com/quote/public"

# Estos routes los sacaste tú antes (según tu debug):
# originRoute=227 (PEN), destinationRoute=59 (USD) en "way=origin"
PEN_ROUTE = 227
USD_ROUTE = 59

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.global66.com",
    "Referer": "https://www.global66.com/",
}

def _calc_rate_pen_per_usd(origin_amount: float, dest_amount: float) -> float | None:
    # rate = PEN / USD
    if not origin_amount or not dest_amount:
        return None
    if dest_amount == 0:
        return None
    return float(origin_amount) / float(dest_amount)

async def scrap_global66():
    casa = "global66"
    url = "https://www.global66.com/pe/envios-de-dinero/"
    payment_type = "WIRE_TRANSFER"  # puedes estandarizar esto
    amount_pen = 1000               # monto estándar para cotizar

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
            # 1) Cotización PEN -> USD (para obtener "venta" PEN/USD)
            r1 = await client.get(API, params={
                "originRoute": PEN_ROUTE,
                "destinationRoute": USD_ROUTE,
                "amount": amount_pen,
                "way": "origin",
                "paymentType": payment_type,
            })
            r1.raise_for_status()
            j1 = r1.json()
            q1 = (j1 or {}).get("quoteData") or {}
            rate_sell = _calc_rate_pen_per_usd(q1.get("originAmount"), q1.get("destinationAmount"))

            # 2) Cotización USD -> PEN (para obtener "compra" PEN/USD)
            #    Aquí cotizamos 300 USD -> PEN (monto estándar)
            amount_usd = 300
            r2 = await client.get(API, params={
                "originRoute": USD_ROUTE,
                "destinationRoute": PEN_ROUTE,
                "amount": amount_usd,
                "way": "origin",
                "paymentType": payment_type,
            })
            r2.raise_for_status()
            j2 = r2.json()
            q2 = (j2 or {}).get("quoteData") or {}

            # Si origin es USD y destino PEN: destAmount = PEN, originAmount = USD
            # Queremos PEN/USD => destAmount / originAmount
            rate_buy = _calc_rate_pen_per_usd(q2.get("destinationAmount"), q2.get("originAmount"))

        compra = normalize_rate(str(rate_buy)) if rate_buy is not None else None
        venta  = normalize_rate(str(rate_sell)) if rate_sell is not None else None

        cerrado = (compra is None and venta is None)

        return {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": "cerrado" if cerrado else "abierto",
            # opcional: para transparencia
            "meta": {"paymentType": payment_type, "amount_pen": amount_pen},
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
