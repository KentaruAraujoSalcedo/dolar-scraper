import re
import httpx
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _to_float(s: str) -> float:
    return float(s.replace(",", ".").strip())

def _extract_buy_sell(html: str):
    # 1) captura candidatos tipo tasa
    hits = []
    for m in RATE_RE.finditer(html):
        raw = m.group(0)
        try:
            x = _to_float(raw)
        except Exception:
            continue
        # filtra números que no sean tipo de cambio (evita 0.118, 5.153, 2.000, 7.000)
        if 2.5 <= x <= 5.5:
            hits.append((m.start(), x, raw))

    if len(hits) < 2:
        return None, None

    # 2) busca parejas cercanas (misma sección)
    pairs = []
    for i in range(len(hits) - 1):
        p1, x1, r1 = hits[i]
        p2, x2, r2 = hits[i + 1]
        if p2 - p1 <= 500:
            buy, sell = (x1, x2) if x1 <= x2 else (x2, x1)

            # score: preferir formatos con 4 decimales (3.3500)
            score = 0
            if len(r1.split(".")[-1]) == 4 or len(r1.split(",")[-1]) == 4:
                score += 1
            if len(r2.split(".")[-1]) == 4 or len(r2.split(",")[-1]) == 4:
                score += 1

            pairs.append((score, buy, sell))

    if pairs:
        pairs.sort(key=lambda t: (-t[0], t[1]))  # mayor score primero
        return pairs[0][1], pairs[0][2]

    # 3) fallback: dos primeros candidatos únicos
    uniq = []
    for _, x, _ in hits:
        if x not in uniq:
            uniq.append(x)
        if len(uniq) >= 2:
            buy, sell = (uniq[0], uniq[1]) if uniq[0] <= uniq[1] else (uniq[1], uniq[0])
            return buy, sell

    return None, None

async def scrap_cambiosol():
    casa = "cambiosol"
    url = "https://cambiosol.pe/"

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

        out = {
            "casa": casa,
            "url": url,
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
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
