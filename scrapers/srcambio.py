"""Cotizaciones públicas USD/PEN de SrCambio.

La API puede mostrar tasas aunque la casa esté cerrada. Conservamos las
cotizaciones, pero indicamos explícitamente si la casa está abierta.
"""

import httpx

from scrapers.utils import normalize_rate


async def scrap_srcambio():
    casa = "srcambio"
    url = "https://srcambio.pe/"
    endpoint = "https://novodivisaspro.pseperu.pro/api/digital/public/tc"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9",
        "Origin": "https://srcambio.pe",
        "Referer": url,
        "X-Digital-Tenant": "sr-cambio",
    }

    def resultado(compra=None, venta=None, estado="error", error=None, abierto=None):
        salida = {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": estado,
        }
        if abierto is not None:
            salida["abierto"] = abierto
        if error:
            salida["error"] = error
        return salida

    try:
        async with httpx.AsyncClient(
            headers=headers, timeout=20, follow_redirects=True
        ) as client:
            respuesta = await client.get(endpoint)
            respuesta.raise_for_status()
            data = respuesta.json()

        if not isinstance(data, dict):
            return resultado(error="La API no devolvió un objeto JSON")

        if data.get("moneda") != "USD":
            return resultado(error="La API no devolvió una cotización USD")

        if data.get("disponible") is not True:
            return resultado(estado="no_disponible")

        abierto = data.get("abierto")
        if not isinstance(abierto, bool):
            return resultado(error="La API no informó un estado de atención válido")

        compra_raw = data.get("compra")
        venta_raw = data.get("venta")
        compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
        venta = normalize_rate(str(venta_raw)) if venta_raw is not None else None

        if (
            compra is None
            or venta is None
            or compra <= 0
            or venta <= 0
            or compra > venta
        ):
            return resultado(error="Tasas de compra o venta ausentes o inválidas")

        # La página de SrCambio presenta las tasas aun estando cerrada.
        # No interpretamos serverTime como la fecha de actualización del precio.
        return resultado(
            compra=compra,
            venta=venta,
            estado="abierto" if abierto else "cerrado",
            abierto=abierto,
        )

    except httpx.HTTPStatusError as exc:
        return resultado(error=f"La API respondió HTTP {exc.response.status_code}")
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return resultado(
            error=f"No se pudo consultar o interpretar SrCambio: {type(exc).__name__}"
        )
