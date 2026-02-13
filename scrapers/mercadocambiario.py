import httpx
from scrapers.utils import normalize_rate

def _percentile(values, p: float):
    """p en [0..1]. Devuelve percentil con método nearest-rank."""
    if not values:
        return None
    vals = sorted(values)
    # nearest rank: ceil(p*n) - 1
    n = len(vals)
    idx = int((p * n) + 0.999999) - 1
    if idx < 0:
        idx = 0
    if idx >= n:
        idx = n - 1
    return vals[idx]

async def scrap_mercadocambiario():
    casa = "MercadoCambiario"
    url = "https://www.mercadocambiario.pe/"
    endpoint_orders = "https://www.mercadocambiario.pe/api/order/get/actives-all"
    endpoint_admin = "https://www.mercadocambiario.pe/api/mercado/get/admin-data"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.mercadocambiario.pe",
        "Referer": "https://www.mercadocambiario.pe/",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=25, follow_redirects=True) as client:
            # 1) open/close (estado del mercado)
            admin_open = None
            try:
                ra = await client.post(endpoint_admin, json={})
                ra.raise_for_status()
                admin = ra.json()
                if isinstance(admin, dict):
                    admin_open = admin.get("open")
            except Exception:
                admin_open = None  # no rompe el scraper

            # 2) órdenes ejecutadas / recientes
            r = await client.post(endpoint_orders, json={})
            r.raise_for_status()
            data = r.json()

        # Extraer successfulOrders
        successful = []
        if isinstance(data, list):
            for block in data:
                if isinstance(block, dict) and isinstance(block.get("successfulOrders"), list):
                    successful.extend(block["successfulOrders"])
        elif isinstance(data, dict) and isinstance(data.get("successfulOrders"), list):
            successful.extend(data["successfulOrders"])

        # Sacar rates válidos
        rates = []
        for o in successful:
            if not isinstance(o, dict):
                continue
            price = o.get("typeExchangeAmount")
            if price is None:
                continue
            try:
                p = float(price)
            except Exception:
                continue
            if 2.5 <= p <= 5.5:
                rates.append(p)

        if not rates:
            # Si no hay rates, lo marcamos cerrado (o error suave)
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "cerrado" if admin_open is False else "error",
                "source": "successfulOrders",
                "error": "No hay successfulOrders con typeExchangeAmount válido.",
            }

        # Definimos compra/venta por percentiles para crear spread robusto
        # 10% bajo = "venta" (más barato), 90% alto = "compra" (más caro)
        venta_raw = _percentile(rates, 0.10)
        compra_raw = _percentile(rates, 0.90)

        compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
        venta  = normalize_rate(str(venta_raw)) if venta_raw is not None else None

        # Asegurar orden lógico
        if isinstance(compra, (int, float)) and isinstance(venta, (int, float)) and compra < venta:
            # si por alguna razón quedó invertido, swap
            compra, venta = venta, compra

        estado = "abierto"
        if admin_open is False:
            estado = "cerrado"
        if compra is None or venta is None:
            estado = "error"

        return {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": estado,
            "source": "successfulOrders_percentiles",
            "open": admin_open,
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
