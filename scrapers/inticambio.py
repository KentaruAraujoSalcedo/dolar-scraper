import re
import httpx
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _to_float(s: str) -> float | None:
    try:
        return float((s or "").strip().replace(",", "."))
    except Exception:
        return None

def _extract_two_rates(html: str):
    # toma tasas razonables y únicas (evita repetir)
    vals = []
    for m in RATE_RE.finditer(html):
        raw = m.group(0).replace(",", ".")
        x = _to_float(raw)
        if x is None:
            continue
        if 2.5 <= x <= 5.5:
            if raw not in vals:
                vals.append(raw)
        if len(vals) >= 2:
            break
    if len(vals) < 2:
        return None, None
    a = _to_float(vals[0])
    b = _to_float(vals[1])
    if a is None or b is None:
        return None, None
    buy, sell = (a, b) if a <= b else (b, a)
    return buy, sell

async def scrap_inticambio():
    casa = "IntiCambio"
    url = "https://inticambio.pe/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": url,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text or ""

        buy, sell = _extract_two_rates(html)

        compra = normalize_rate(str(buy)) if buy is not None else None
        venta  = normalize_rate(str(sell)) if sell is not None else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        # Si no logró identificar, lo marco como error para que lo veas
        if compra is None or venta is None:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "No se pudieron identificar 2 tasas en el HTML.",
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
