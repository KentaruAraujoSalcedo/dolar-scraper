import os
import json
import asyncio
import httpx
from scrapers.utils import normalize_rate

DEBUG = os.getenv("DEBUG_SAFEX") == "1"

def _debug_dump(text: str, meta: dict):
    if not DEBUG:
        return
    os.makedirs("data/debug", exist_ok=True)
    with open("data/debug/safex_last.txt", "w", encoding="utf-8") as f:
        f.write(text or "")
    with open("data/debug/safex_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

async def scrap_safex():
    casa = "Safex"
    url = "https://www.safex.pe/"
    endpoint = "https://www.safex.pe/cotizacion/cotizacion.php"

    headers_home = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    # Más parecido a XHR
    headers_api = {
        "User-Agent": headers_home["User-Agent"],
        "Accept-Language": headers_home["Accept-Language"],
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
        "Origin": url.rstrip("/"),
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    last_payload = None
    last_text = None

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # 1) Prewarm: cargar home para cookies/sesión
            await client.get(url, headers=headers_home)

            # 2) Intentos al endpoint
            for attempt in range(1, 4):
                r = await client.get(endpoint, headers=headers_api)
                status = r.status_code
                final_url = str(r.url)
                last_text = r.text or ""

                # intenta JSON
                payload = None
                try:
                    payload = r.json()
                except Exception:
                    try:
                        payload = json.loads(last_text)
                    except Exception:
                        payload = None

                last_payload = payload

                # éxito esperado
                if isinstance(payload, dict) and payload.get("response") == "success":
                    data = payload.get("data") or {}
                    compra_raw = data.get("precCompra")
                    venta_raw  = data.get("precVenta")

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

                # si devuelve error4, es señal de falta de sesión / bloqueo: reintenta con backoff
                if isinstance(payload, dict) and payload.get("response") == "error4":
                    _debug_dump(last_text, {
                        "casa": casa,
                        "attempt": attempt,
                        "status_code": status,
                        "final_url": final_url,
                        "reason": "error4",
                        "payload": payload,
                    })
                    await asyncio.sleep(0.35 * attempt)
                    continue

                # cualquier otra cosa inesperada: no sigas pegando mucho
                _debug_dump(last_text, {
                    "casa": casa,
                    "attempt": attempt,
                    "status_code": status,
                    "final_url": final_url,
                    "reason": "unexpected_payload",
                    "payload": payload,
                })
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error_type": "api_unexpected",
                    "error": f"Respuesta inesperada: status={status} payload={payload!r}",
                }

        # si salió del loop por error4 repetido
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error_type": "blocked_or_session",
            "error": f"Safex devolvió error4 tras reintentos. payload={last_payload!r}",
        }

    except Exception as e:
        _debug_dump(last_text or "", {
            "casa": casa,
            "reason": "exception",
            "exception_type": type(e).__name__,
            "exception_message": str(e),
            "last_payload": last_payload,
        })
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error_type": "error",
            "exception_type": type(e).__name__,
            "exception_message": str(e),
            "error": f"No se pudo scrapear: {e}",
        }
