"""Cotización de Cambio Mundial desde el JSON utilizado por su página pública.

La web mostró el 07/11/2026 la tasa REGULAR para montos >= USD 1,000.
Si cambia el endpoint o el proveedor restringe el acceso automatizado,
se devuelve un error diagnosticable sin intentar sortear esa restricción.
"""

import httpx

from scrapers.utils import normalize_rate


CASA = "cambiomundial"
URL = "https://www.cambiomundial.com/"
ENDPOINT = "https://www.cambiomundial.com/backend/tasaCambio/daily"


def _fallo(codigo: str, motivo: str, *, bloqueado: bool = False) -> dict:
    return {
        "casa": CASA,
        "url": URL,
        "compra": None,
        "venta": None,
        "estado": "bloqueado" if bloqueado else "error",
        "source": "blocked" if bloqueado else "missing",
        "error_type": codigo,
        "error": motivo,
    }


def _es_desafio(texto: str) -> bool:
    """Detecta páginas de desafío; no confunde el JSON normal con un bloqueo."""
    contenido = (texto or "").lower()
    return any(marca in contenido for marca in (
        "just a moment", "checking your browser", "verify you are human",
        "cf-chl-", "/cdn-cgi/challenge-platform/", "attention required",
    ))


def _tasa_regular(datos: object) -> tuple[float | None, float | None]:
    """Solo utiliza el registro REGULAR: nunca confunde tasa diferenciada."""
    if not isinstance(datos, list):
        return None, None

    for registro in datos:
        if not isinstance(registro, dict):
            continue
        if str(registro.get("tipoTasa", "")).strip().upper() != "REGULAR":
            continue

        compra = normalize_rate(registro.get("buy"))
        venta = normalize_rate(registro.get("sell"))
        if compra is None or venta is None or compra > venta:
            return None, None
        return compra, venta

    return None, None


async def scrap_cambiomundial() -> dict:
    """Devuelve el esquema esperado por run_scrapers.py."""
    cabeceras = {
        "Accept": "application/json",
        "Accept-Language": "es-PE,es;q=0.9",
    }
    timeout = httpx.Timeout(20.0, connect=10.0)

    try:
        async with httpx.AsyncClient(
            headers=cabeceras, timeout=timeout, follow_redirects=True
        ) as cliente:
            respuesta = await cliente.get(ENDPOINT)
    except httpx.TimeoutException:
        return _fallo("timeout", "Tiempo de espera agotado al consultar la API")
    except httpx.RequestError as exc:
        return _fallo("error", f"Fallo de conexión ({type(exc).__name__})")

    if respuesta.status_code in (403, 429):
        return _fallo(
            f"blocked_{respuesta.status_code}",
            f"Acceso rechazado por Cambio Mundial (HTTP {respuesta.status_code})",
            bloqueado=True,
        )

    if _es_desafio(respuesta.text):
        return _fallo(
            "blocked_cloudflare", "El proveedor solicita una comprobación de acceso",
            bloqueado=True,
        )

    if respuesta.status_code != 200:
        return _fallo(
            f"http_{respuesta.status_code}",
            f"El endpoint respondió HTTP {respuesta.status_code}",
        )

    try:
        datos = respuesta.json()
    except ValueError:
        return _fallo("parse_error", "El endpoint no devolvió JSON válido")

    compra, venta = _tasa_regular(datos)
    if compra is None or venta is None:
        return _fallo("missing_rates", "No se encontró una tasa REGULAR válida con buy y sell")

    return {
        "casa": CASA,
        "url": URL,
        "compra": compra,
        "venta": venta,
        "estado": "abierto",
        "source": "httpx",
    }
