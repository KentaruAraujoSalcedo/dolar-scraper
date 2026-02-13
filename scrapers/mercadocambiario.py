import httpx
from scrapers.utils import normalize_rate

async def scrap_mercadocambiario():
    casa = "MercadoCambiario"
    url = "https://www.mercadocambiario.pe/"
    endpoint = "https://www.mercadocambiario.pe/api/order/get/actives-all"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Origin": "https://www.mercadocambiario.pe",
        "Referer": "https://www.mercadocambiario.pe/",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=25, follow_redirects=True) as client:
            # warmup cookies (ayuda con 403 intermitente)
            await client.get(url)

            r = await client.post(endpoint, json={})
            r.raise_for_status()
            data = r.json()

        rates = []
        if isinstance(data, list):
            for block in data:
                if not isinstance(block, dict):
                    continue
                for o in block.get("successfulOrders", []) or []:
                    if not isinstance(o, dict):
                        continue
                    x = o.get("typeExchangeAmount")
                    try:
                        p = float(x)
                    except Exception:
                        continue
                    # rango realista PEN/USD
                    if 2.8 <= p <= 4.2:
                        rates.append(p)

        if not rates:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "source": "actives-all_minmax",
                "error": "No se encontraron rates válidos en successfulOrders.",
            }

        # ✅ Lo que muestra la web:
        venta_raw = min(rates)   # mejor tasa para vender USD (más baja)
        compra_raw = max(rates)  # mejor tasa para comprar USD (más alta)

        compra = normalize_rate(str(compra_raw))
        venta  = normalize_rate(str(venta_raw))

        return {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": "abierto",
            "source": "actives-all_successfulOrders_minmax",
            "n_rates": len(rates),
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
