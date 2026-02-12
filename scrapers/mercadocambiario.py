import httpx
from scrapers.utils import normalize_rate

async def scrap_mercadocambiario():
    casa = "MercadoCambiario"
    url = "https://www.mercadocambiario.pe/"
    endpoint = "https://www.mercadocambiario.pe/api/order/get/actives-all"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.mercadocambiario.pe",
        "Referer": "https://www.mercadocambiario.pe/",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.post(endpoint, json={})
            r.raise_for_status()
            data = r.json()

        # Estructura observada: lista de objetos, uno con "currentOrders"
        current_orders = []
        if isinstance(data, list):
            for block in data:
                if isinstance(block, dict) and isinstance(block.get("currentOrders"), list):
                    current_orders.extend(block["currentOrders"])

        if not current_orders:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "No se encontró currentOrders en la respuesta.",
            }

        buys = []
        sells = []

        for o in current_orders:
            if not isinstance(o, dict):
                continue
            op = (o.get("typeOperation") or "").lower().strip()
            price = o.get("typeExchangeAmount")

            if price is None:
                continue

            try:
                p = float(price)
            except Exception:
                continue

            # filtro de seguridad (tipo de cambio razonable)
            if not (2.5 <= p <= 5.5):
                continue

            if op == "buy":
                buys.append(p)
            elif op == "sell":
                sells.append(p)

        # “mejor” compra = máximo buy, “mejor” venta = mínimo sell
        compra = max(buys) if buys else None
        venta = min(sells) if sells else None

        compra_n = normalize_rate(str(compra)) if compra is not None else None
        venta_n  = normalize_rate(str(venta)) if venta is not None else None

        cerrado = (compra_n is None and venta_n is None) or (compra_n == 0.0 and venta_n == 0.0)

        estado = "cerrado" if cerrado else "abierto"
        if compra_n is None or venta_n is None:
            estado = "error"

        out = {
            "casa": casa,
            "url": url,
            "compra": compra_n,
            "venta": venta_n,
            "estado": estado,
        }

        if estado == "error":
            out["error"] = "No se pudo calcular compra/venta (faltan órdenes buy o sell)."

        return out

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
