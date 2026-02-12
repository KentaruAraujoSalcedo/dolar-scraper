import re
import httpx
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _to_float(s: str) -> float:
    return float((s or "").replace(",", ".").strip())

def _extract_pair(html: str):
    # toma solo tasas razonables y únicas manteniendo orden
    vals = []
    for m in RATE_RE.finditer(html):
        raw = m.group(0)
        try:
            x = _to_float(raw)
        except Exception:
            continue
        if 2.5 <= x <= 5.5:
            if x not in vals:
                vals.append(x)
        if len(vals) >= 2:
            break

    if len(vals) < 2:
        return None, None

    buy, sell = (vals[0], vals[1]) if vals[0] <= vals[1] else (vals[1], vals[0])
    return buy, sell

async def scrap_smartdollar():
    casa = "SmartDollar"
    url = "https://www.smartdollar.pe/"

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

        buy, sell = _extract_pair(html)

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
