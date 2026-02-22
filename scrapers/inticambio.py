import re
import os
import json
import asyncio
import httpx
from scrapers.utils import normalize_rate

DEBUG = os.getenv("DEBUG_INTICAMBIO") == "1"

# Captura 3.345 / 3,345 / 3.35 (por si cambian a 2 decimales)
RATE_RE = re.compile(r"\b\d[.,]\d{2,4}\b")

# Contexto: busca la tasa cerca a la palabra Compra/Venta
BUY_CTX_RE  = re.compile(r"compra.{0,80}?(\d[.,]\d{2,4})", re.IGNORECASE | re.DOTALL)
SELL_CTX_RE = re.compile(r"venta.{0,80}?(\d[.,]\d{2,4})",  re.IGNORECASE | re.DOTALL)

def _to_float(s: str) -> float | None:
    try:
        return float((s or "").strip().replace(",", "."))
    except Exception:
        return None

def _pick_rate_near_keyword(html: str, pattern: re.Pattern) -> float | None:
    m = pattern.search(html)
    if not m:
        return None
    x = _to_float(m.group(1))
    if x is None:
        return None
    if 2.8 <= x <= 4.5:
        return x
    return None

def _extract_from_context(html: str) -> tuple[float | None, float | None]:
    buy = _pick_rate_near_keyword(html, BUY_CTX_RE)
    sell = _pick_rate_near_keyword(html, SELL_CTX_RE)
    if buy is not None and sell is not None:
        return (buy, sell) if buy <= sell else (sell, buy)
    return None, None

def _extract_fallback_two_rates(html: str) -> tuple[float | None, float | None]:
    vals: list[float] = []
    for m in RATE_RE.finditer(html):
        x = _to_float(m.group(0))
        if x is None:
            continue
        if 2.8 <= x <= 4.5:
            vals.append(x)
    vals = sorted({round(v, 4) for v in vals})
    if len(vals) < 2:
        return None, None
    return vals[0], vals[-1]

def _looks_blocked(html: str) -> str | None:
    h = (html or "").lower()
    if "un momento" in h or "just a moment" in h:
        return "blocked_cloudflare"
    if "cf-chl" in h or "cloudflare" in h:
        return "blocked_cloudflare"
    if "access denied" in h or "forbidden" in h:
        return "blocked"
    return None

def _debug_dump(html: str, meta: dict):
    if not DEBUG:
        return
    os.makedirs("data/debug", exist_ok=True)
    with open("data/debug/inticambio_last.html", "w", encoding="utf-8") as f:
        f.write(html or "")
    with open("data/debug/inticambio_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

async def scrap_inticambio():
    casa = "inticambio"
    url = "https://inticambio.pe/"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": url,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    last_err = None

    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=20,
                follow_redirects=True,
            ) as client:
                r = await client.get(url)

            status = r.status_code
            final_url = str(r.url)
            html = r.text or ""

            blocked = _looks_blocked(html)
            if blocked:
                _debug_dump(html, {
                    "casa": casa,
                    "url": url,
                    "final_url": final_url,
                    "status_code": status,
                    "attempt": attempt,
                    "reason": blocked,
                    "len_html": len(html),
                })
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error_type": blocked,
                    "error": f"Página bloqueada ({blocked}). status={status}. final_url={final_url}",
                }

            # 1) extracción robusta por contexto (Compra/Venta)
            buy, sell = _extract_from_context(html)

            # 2) fallback min/max tasas razonables
            if buy is None or sell is None:
                buy, sell = _extract_fallback_two_rates(html)

            compra = normalize_rate(str(buy)) if buy is not None else None
            venta  = normalize_rate(str(sell)) if sell is not None else None

            if compra is None or venta is None:
                _debug_dump(html, {
                    "casa": casa,
                    "url": url,
                    "final_url": final_url,
                    "status_code": status,
                    "attempt": attempt,
                    "reason": "parse_error",
                    "len_html": len(html),
                })
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error_type": "parse_error",
                    "error": f"No se pudieron identificar 2 tasas. status={status}. final_url={final_url}. len={len(html)}",
                }

            cerrado = (compra == 0.0 and venta == 0.0)

            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
                "estado": "cerrado" if cerrado else "abierto",
            }

        except Exception as e:
            last_err = e
            await asyncio.sleep(0.25 * attempt)

    return {
        "casa": casa,
        "url": url,
        "compra": None,
        "venta": None,
        "estado": "error",
        "error_type": "error",
        "exception_type": type(last_err).__name__ if last_err else None,
        "exception_message": str(last_err) if last_err else "unknown",
        "error": f"No se pudo scrapear tras reintentos: {last_err}",
    }
