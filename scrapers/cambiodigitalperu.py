"""CambioDigitalPerú: cotizaciones USD/PEN desde su API pública.

Ruta observada en DevTools el 6 de noviembre de 2026:
    https://novodivisaspro.pseperu.pro/api/digital/public/tc

La respuesta incluye: disponible, compra, venta, moneda, abierto, serverTime.
No utiliza tokens, cookies ni datos de otros proveedores.
"""

import httpx

from scrapers.utils import normalize_rate


CASA = "cambiodigitalperu"
URL = "https://cambiodigitalperu.com"
ENDPOINT = "https://novodivisaspro.pseperu.pro/api/digital/public/tc"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "es-PE,es;q=0.9",
    "Origin": URL,
    "Referer": URL + "/",
}


def _error(codigo, mensaje, *, blocked=False):
    """Devuelve un resultado compatible con los diagnósticos del proyecto."""
    return {
        "casa": CASA,
        "url": URL,
        "compra": None,
        "venta": None,
        "estado": "error",
        "source": "blocked" if blocked else "missing",
        "error_type": codigo,
        "error": mensaje,
    }


async def scrap_cambiodigitalperu():
    try:
        timeout = httpx.Timeout(15.0, connect=6.0)
        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            response = await client.get(ENDPOINT)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            return _error("parse_error", "La API no devolvió un objeto JSON")

        # No suponer que otra moneda corresponde a USD/PEN.
        if str(data.get("moneda", "")).upper() != "USD":
            return _error("moneda_invalida", "La API no informó una cotización USD")

        # 'disponible' indica si la cotización está disponible en la API.
        if data.get("disponible") is not True:
            return _error("no_disponible", "La API indicó que la tasa no está disponible")

        compra = normalize_rate(data.get("compra"))
        venta = normalize_rate(data.get("venta"))
        if compra is None or venta is None:
            return _error("missing_rates", "Falta una tasa de compra o venta válida")
        if compra > venta:
            return _error("tasas_invertidas", "Compra supera venta; requiere revisión")

        # 'abierto' es el estado operativo del proveedor, distinto de
        # 'disponible'. La web puede informar tasas aun cuando esté cerrado.
        abierto = data.get("abierto")
        estado = "abierto" if abierto is True else "cerrado" if abierto is False else "desconocido"

        resultado = {
            "casa": CASA,
            "url": URL,
            "compra": compra,
            "venta": venta,
            "estado": estado,
        }
        if isinstance(abierto, bool):
            resultado["operacion_abierta"] = abierto
        if isinstance(data.get("serverTime"), str):
            # Se conserva tal cual; el valor no declara zona horaria.
            resultado["timestamp"] = data["serverTime"]
        return resultado

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403, 429):
            return _error(
                f"blocked_{status}",
                f"El proveedor rechazó la solicitud (HTTP {status})",
                blocked=True,
            )
        return _error(f"http_{status}", f"La API respondió HTTP {status}")
    except httpx.TimeoutException:
        return _error("timeout", "La API no respondió dentro del tiempo límite")
    except httpx.RequestError:
        return _error("network_error", "No se pudo conectar con la API")
    except (ValueError, TypeError):
        return _error("invalid_json", "La API no devolvió un JSON válido")
