import os
import re
from datetime import datetime

import httpx
from scrapers.utils import normalize_rate

# acepta 2 a 4 decimales (3.34 / 3.363 / 3.345)
RATE_RE = re.compile(r"\b\d[.,]\d{2,4}\b", re.I)

BUY_BLOCK_RE  = re.compile(r'id="item_compra".*?<span[^>]*>\s*(\d[.,]\d{2,4})\s*</span>', re.I | re.S)
SELL_BLOCK_RE = re.compile(r'id="item_venta".*?<span[^>]*>\s*(\d[.,]\d{2,4})\s*</span>', re.I | re.S)

def _to_float(s: str):
    s = re.sub(r"[^\d.,]", "", (s or "")).strip()
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def _dump_debug_html(casa: str, html: str) -> str:
    os.makedirs("debug_html", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"debug_html/{casa.lower()}_{ts}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html or "")
    return path

def _extract_buy_sell_from_html(html: str):
    # 1) método estable por IDs
    m_buy = BUY_BLOCK_RE.search(html or "")
    m_sell = SELL_BLOCK_RE.search(html or "")

    buy  = _to_float(m_buy.group(1)) if m_buy else None
    sell = _to_float(m_sell.group(1)) if m_sell else None

    if buy is not None and sell is not None:
        b, s = (buy, sell) if buy <= sell else (sell, buy)
        return b, s

    # 2) fallback: buscar dos números razonables cercanos
    candidates = []
    for m in RATE_RE.finditer(html or ""):
        x = _to_float(m.group(0))
        if x is None:
            continue
        if 2.8 <= x <= 4.2:
            candidates.append((m.start(), x))

    for i in range(len(candidates) - 1):
        pos1, x1 = candidates[i]
        pos2, x2 = candidates[i + 1]
        if (pos2 - pos1) <= 800:
            b, s = (x1, x2) if x1 <= x2 else (x2, x1)
            if (s - b) <= 0.25:
                return b, s

    return None, None

async def scrap_securex():
    url = "https://securex.pe/"
    casa = "securex"

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

    try:
        async with httpx.AsyncClient(headers=headers, timeout=25, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text or ""

        buy, sell = _extract_buy_sell_from_html(html)

        compra = normalize_rate(str(buy)) if buy is not None else None
        venta  = normalize_rate(str(sell)) if sell is not None else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        out = {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": "cerrado" if cerrado else "abierto",
        }

        if compra is None or venta is None:
            path = _dump_debug_html(casa, html)
            out["estado"] = "error"
            out["error"] = f"No se pudo identificar compra/venta. Debug HTML: {path}"

        return out

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
