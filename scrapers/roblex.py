import httpx
from scrapers.utils import normalize_rate

async def scrap_roblex():
    casa = "roblex"
    url = "https://roblex.pe/"

    base = "https://operations.roblex.pe"
    active_endpoint = f"{base}/valuation/active-valuation"
    op_endpoint = f"{base}/operation"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Origin": "https://roblex.pe",
        "Referer": "https://roblex.pe/",
    }

    def _assign_rate(result: dict, rates: dict):
        """
        Guarda la tasa según result['type'] en rates dict.
        Esperado: type in {'compra','venta'} y rate string/number.
        """
        t = (result.get("type") or "").strip().lower()
        rate_raw = result.get("rate")
        rate = normalize_rate(str(rate_raw)) if rate_raw is not None else None
        if t in ("compra", "venta") and rate is not None:
            rates[t] = rate

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            # 1) Valuation activa
            r = await client.get(active_endpoint)
            r.raise_for_status()
            active = r.json()

            valuation_id = active.get("id")
            currency_id = active.get("currencyId")
            exchange_currency_id = active.get("exchangeCurrencyId")

            if not (valuation_id and currency_id and exchange_currency_id):
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error": "active-valuation no trajo id/currencyId/exchangeCurrencyId",
                }

            rates = {}  # {'compra': x, 'venta': y}

            # 2) Operación en un sentido
            params_1 = {
                "valuationId": valuation_id,
                "originCurrencyId": currency_id,
                "destinationCurrencyId": exchange_currency_id,
                "amount": 100,
                "active": "S",
            }
            r1 = await client.get(op_endpoint, params=params_1)
            r1.raise_for_status()
            _assign_rate(r1.json(), rates)

            # 3) Operación en el sentido inverso (para capturar el otro tipo)
            params_2 = {
                "valuationId": valuation_id,
                "originCurrencyId": exchange_currency_id,
                "destinationCurrencyId": currency_id,
                "amount": 100,
                "active": "S",
            }
            r2 = await client.get(op_endpoint, params=params_2)
            r2.raise_for_status()
            _assign_rate(r2.json(), rates)

        compra = rates.get("compra")
        venta = rates.get("venta")

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        # Si faltó una de las dos, lo marco como error para que lo detectes rápido
        if compra is None or venta is None:
            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
                "estado": "error",
                "error": f"No se pudo obtener ambas tasas. Encontrado: {rates}",
            }

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
