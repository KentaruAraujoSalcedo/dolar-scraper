import re
import httpx
from scrapers.utils import normalize_rate

URL = "https://cambiox.pe/"
CASA = "CambioX"

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _to_float(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except Exception:
        return None

def _extract_buy_sell(html: str):
    # encuentra todas las tasas candidatas (2.5–5.5), dedupe manteniendo orden
    vals = []
    for m in RATE_RE.finditer(html or ""):
        raw = m.group(0)
        x = _to_float(raw)
        if x is None:
            continue
        if 2.5 <= x <= 5.5:
            if x not in vals:
                vals.append(x)

    # lo normal aquí es que queden [compra, venta]
    if len(vals) >= 2:
        buy, sell = (vals[0], vals[1]) if vals[0] <= vals[1] else (vals[1], vals[0])
        return buy, sell

    return None, None

async def scrap_cambiox():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": URL,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            html = r.text or ""

        buy, sell = _extract_buy_sell(html)

        compra = normalize_rate(str(buy)) if buy is not None else None
        venta  = normalize_rate(str(sell)) if sell is not None else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        out = {
            "casa": CASA,
            "url": URL,
            "compra": compra,
            "venta": venta,
            "estado": "cerrado" if cerrado else "abierto",
        }

        if compra is None or venta is None:
            out["estado"] = "error"
            out["error"] = "No se pudo identificar compra/venta de forma confiable (HTML cambió)."

        return out

    except Exception as e:
        return {
            "casa": CASA,
            "url": URL,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
