import re
import httpx
from scrapers.utils import normalize_rate

URL = "https://perudolar.pe/"
CASA = "PeruDolar"

# más flexible: 3.34 / 3.345 / 3,345
RATE_RE = re.compile(r"\b\d[.,]\d{2,4}\b")

# captura cerca del texto Compra/Venta
BUY_CTX_RE  = re.compile(r"compra.{0,120}?(\d[.,]\d{2,4})", re.IGNORECASE | re.DOTALL)
SELL_CTX_RE = re.compile(r"venta.{0,120}?(\d[.,]\d{2,4})",  re.IGNORECASE | re.DOTALL)

def _to_float(s: str):
    try:
        return float((s or "").replace(",", ".").strip())
    except Exception:
        return None

def _extract_by_context(html: str):
    mb = BUY_CTX_RE.search(html or "")
    ms = SELL_CTX_RE.search(html or "")
    if not mb or not ms:
        return None, None

    buy = _to_float(mb.group(1))
    sell = _to_float(ms.group(1))

    if buy is None or sell is None:
        return None, None

    # rango razonable PEN/USD
    if not (2.8 <= buy <= 4.5 and 2.8 <= sell <= 4.5):
        return None, None

    return (buy, sell) if buy <= sell else (sell, buy)

def _extract_buy_sell_fallback(html: str):
    # candidatos razonables de tipo de cambio
    candidates = []
    for m in RATE_RE.finditer(html or ""):
        x = _to_float(m.group(0))
        if x is None:
            continue
        if 2.8 <= x <= 4.5:
            candidates.append((m.start(), x))

    # pareja cercana en el HTML (más confiable)
    for i in range(len(candidates) - 1):
        p1, x1 = candidates[i]
        p2, x2 = candidates[i + 1]
        if (p2 - p1) <= 500:
            buy, sell = (x1, x2) if x1 <= x2 else (x2, x1)
            return buy, sell

    # fallback: min/max (evita agarrar dos del mismo valor repetido)
    uniq = sorted({round(x, 4) for _, x in candidates})
    if len(uniq) >= 2:
        return uniq[0], uniq[-1]

    return None, None

async def scrap_perudolar():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": URL,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=25, follow_redirects=True) as client:
            r = await client.get(URL)
            r.raise_for_status()
            html = r.text or ""

        # 1) intento robusto por contexto
        buy, sell = _extract_by_context(html)

        # 2) fallback antiguo si no encontró por contexto
        if buy is None or sell is None:
            buy, sell = _extract_buy_sell_fallback(html)

        compra = normalize_rate(str(buy)) if buy is not None else None
        venta  = normalize_rate(str(sell)) if sell is not None else None

        if compra is None or venta is None:
            return {
                "casa": CASA,
                "url": URL,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error_type": "parse_error",
                "error": "No se pudo identificar compra/venta (selector/contexto no encontrado).",
            }

        cerrado = (compra == 0.0 and venta == 0.0)

        return {
            "casa": CASA,
            "url": URL,
            "compra": compra,
            "venta": venta,
            "estado": "cerrado" if cerrado else "abierto",
        }

    except Exception as e:
        return {
            "casa": CASA,
            "url": URL,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error_type": "error",
            "error": f"No se pudo scrapear: {e}",
        }
