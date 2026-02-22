import re
import httpx
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _to_float(s: str) -> float:
    return float((s or "").replace(",", ".").strip())

async def scrap_dichikash():
    casa = "dichikash"
    url = "https://dichikash.com/"

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

        # extrae tasas del HTML
        nums = []
        for m in RATE_RE.finditer(html):
            s = m.group(0).replace(",", ".")
            try:
                x = _to_float(s)
            except Exception:
                continue
            # filtra rango razonable de tipo de cambio
            if 2.5 <= x <= 5.5:
                nums.append(x)

        # dedupe manteniendo orden
        uniq = []
        for x in nums:
            if x not in uniq:
                uniq.append(x)

        if len(uniq) < 2:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "No se encontraron 2 tasas en el HTML",
            }

        # compra suele ser menor que venta
        buy, sell = (uniq[0], uniq[1]) if uniq[0] <= uniq[1] else (uniq[1], uniq[0])

        compra = normalize_rate(str(buy))
        venta  = normalize_rate(str(sell))

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

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
