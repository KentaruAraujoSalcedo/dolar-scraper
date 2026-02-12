import re
import httpx
from scrapers.utils import normalize_rate

BUY_RE  = re.compile(r"Compra:\s*S/\s*([0-9]+(?:[.,][0-9]{2,4})?)", re.IGNORECASE)
SELL_RE = re.compile(r"Venta:\s*S/\s*([0-9]+(?:[.,][0-9]{2,4})?)", re.IGNORECASE)

def _clean_num(s: str) -> str:
    return (s or "").strip().replace(",", ".")

async def scrap_rissanpe():
    url = "https://www.rissanpe.com/"
    casa = "Rissanpe"

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

        m_buy = BUY_RE.search(html)
        m_sell = SELL_RE.search(html)

        compra = normalize_rate(_clean_num(m_buy.group(1))) if m_buy else None
        venta  = normalize_rate(_clean_num(m_sell.group(1))) if m_sell else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        if compra is None or venta is None:
            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
                "estado": "error",
                "error": "No se encontraron Compra/Venta en el HTML (puede haber cambiado el texto).",
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
