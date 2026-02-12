import re
import httpx
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _to_float(s: str) -> float:
    return float((s or "").strip().replace(",", "."))

def _extract_buy_sell(html: str):
    """
    DollarHouse: el HTML contiene tasas tipo 3.3520 y 3.3590.
    Tomamos la primera pareja cercana de tasas razonables (2.5–5.5).
    """
    candidates = []
    for m in RATE_RE.finditer(html):
        raw = m.group(0)
        try:
            x = _to_float(raw)
        except Exception:
            continue
        if 2.5 <= x <= 5.5:
            candidates.append((m.start(), x))

    # pareja cercana
    for i in range(len(candidates) - 1):
        pos1, x1 = candidates[i]
        pos2, x2 = candidates[i + 1]
        if pos2 - pos1 <= 500:
            buy, sell = (x1, x2) if x1 <= x2 else (x2, x1)
            return buy, sell

    # fallback: dos primeros únicos
    uniq = []
    for _, x in candidates:
        if x not in uniq:
            uniq.append(x)
        if len(uniq) >= 2:
            buy, sell = (uniq[0], uniq[1]) if uniq[0] <= uniq[1] else (uniq[1], uniq[0])
            return buy, sell

    return None, None

async def scrap_dollarhouse():
    casa = "DollarHouse"
    url = "https://app.dollarhouse.pe/"

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
        async with httpx.AsyncClient(headers=headers, timeout=25, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text or ""

        buy, sell = _extract_buy_sell(html)

        compra = normalize_rate(str(buy)) if buy is not None else None
        venta  = normalize_rate(str(sell)) if sell is not None else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        if compra is None or venta is None:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "No se pudo identificar compra/venta de forma confiable (HTML cambió).",
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
