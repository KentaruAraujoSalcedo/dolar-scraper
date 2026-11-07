"""Cotizaciones públicas de Mercado Cambiario.

Usa el libro de órdenes vigente y el TradeFee que devuelve la configuración
pública. No reutiliza operaciones finalizadas como cotizaciones actuales.

IMPORTANTE: El acceso desde GitHub Actions puede seguir recibiendo HTTP 403.
Este módulo NO intenta superar las restricciones de acceso del proveedor.
"""

from decimal import Decimal, InvalidOperation

import httpx

from scrapers.utils import normalize_rate

CASA = "mercadocambiario"
HOME = "https://www.mercadocambiario.pe/"
ORDERS_ENDPOINT = "https://www.mercadocambiario.pe/api/order/get/actives-all"
CONFIG_ENDPOINT = "https://www.mercadocambiario.pe/api/mercado/get/admin-data"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-PE,es;q=0.9",
    "Content-Type": "application/json",
    "Origin": HOME.rstrip("/"),
    "Referer": HOME,
}


def _decimal(value):
    """Interpreta solo números finitos (sin bool, NaN ni infinito)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def _calculate_rates(orders_payload, config_payload):
    """Devuelve (compra, venta) desde la perspectiva de la CASA DE CAMBIO.

    - 'buy' corresponde al precio base que el mercado paga por USD.
    - 'sell' corresponde al precio base que cobra por USD.
    - TradeFee.amount se resta de compra y se suma a venta.
    - Solo considera órdenes con amountLeft > 0.
    
    Falla de forma segura si faltan órdenes o la comisión dinámica.
    """
    if not isinstance(orders_payload, list) or not isinstance(config_payload, dict):
        raise ValueError("respuesta_json_inesperada")

    groups = [block.get("currentOrders") for block in orders_payload
              if isinstance(block, dict) and isinstance(block.get("currentOrders"), list)]
    if len(groups) != 1:
        raise ValueError("currentOrders_no_disponible")

    active_buy = []
    active_sell = []
    for order in groups[0]:
        if not isinstance(order, dict):
            continue
        remaining = _decimal(order.get("amountLeft"))
        rate = _decimal(order.get("typeExchangeAmount"))
        if remaining is None or remaining <= 0 or rate is None or not Decimal("2.8") <= rate <= Decimal("4.2"):
            continue
        if order.get("typeOperation") == "buy":
            active_buy.append(rate)
        elif order.get("typeOperation") == "sell":
            active_sell.append(rate)

    if not active_buy or not active_sell:
        raise ValueError("ordenes_activas_insuficientes")

    trade_fees = config_payload.get("TradeFee")
    if not isinstance(trade_fees, list) or len(trade_fees) != 1 or not isinstance(trade_fees[0], dict):
        raise ValueError("TradeFee_no_disponible")
    fee = _decimal(trade_fees[0].get("amount"))
    if fee is None or not Decimal("0") <= fee <= Decimal("0.05"):
        raise ValueError("TradeFee_fuera_de_rango")

    compra = max(active_buy) - fee
    venta = min(active_sell) + fee
    if not (Decimal("2.8") <= compra < venta <= Decimal("4.2")):
        raise ValueError("tasas_incoherentes")

    return compra, venta


def _failed(reason, error_type="error"):
    return {
        "casa": CASA,
        "url": HOME,
        "compra": None,
        "venta": None,
        "estado": "error",
        "error_type": error_type,
        "error": reason,
        "source": "actives-all_httpx_orderbook_fee",
    }


async def scrap_mercadocambiario():
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=25, follow_redirects=True) as client:
            # Mantener la visita inicial como en el scraper original.
            await client.get(HOME)
            orders_response = await client.post(ORDERS_ENDPOINT, json={})
            orders_response.raise_for_status()
            config_response = await client.post(CONFIG_ENDPOINT, json={})
            config_response.raise_for_status()
            orders_payload = orders_response.json()
            config_payload = config_response.json()

        compra, venta = _calculate_rates(orders_payload, config_payload)
        return {
            "casa": CASA,
            "url": HOME,
            "compra": normalize_rate(str(compra)),
            "venta": normalize_rate(str(venta)),
            "estado": "abierto",
            "source": "actives-all_httpx_orderbook_fee",
        }
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        reason = f"blocked_403: proveedor rechazó acceso ({status})" if status == 403 else f"http_{status}: respuesta del proveedor"
        return _failed(reason, "blocked_403" if status == 403 else f"http_{status}")
    except (httpx.RequestError, ValueError) as exc:
        # No registrar cuerpos de respuesta, cookies ni cabeceras privadas.
        reason = str(exc) if isinstance(exc, ValueError) else f"network_{type(exc).__name__}"
        return _failed(reason)
    except Exception as exc:
        return _failed(f"unexpected_{type(exc).__name__}")
