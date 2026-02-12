import re
import httpx
from scrapers.utils import normalize_rate

def _clean_num(txt: str) -> str:
    return re.sub(r"[^\d.,]", "", (txt or "")).replace(",", ".")

def _extract_first_span(html: str, field_class: str) -> str | None:
    """
    Extrae el primer número dentro del bloque:
      <div class="views-field ... {field_class}"> ... <span ...>3.3500</span>
    """
    # aislamos el div del campo (compra o venta)
    m = re.search(
        rf'<div[^>]+class="[^"]*{re.escape(field_class)}[^"]*"[^>]*>(.*?)</div>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None

    block = m.group(1)

    # preferimos cantant si existe; si no, cualquier span con número
    m2 = re.search(r'<span[^>]+class="[^"]*\bcantant\b[^"]*"[^>]*>([^<]+)</span>', block, flags=re.I)
    if not m2:
        m2 = re.search(r'<span[^>]+class="[^"]*\bcant\b[^"]*"[^>]*>([^<]+)</span>', block, flags=re.I)
    if not m2:
        # último fallback: primer número tipo 3.3500 en el bloque
        m2 = re.search(r"\b\d[.,]\d{3,4}\b", block)

    return m2.group(1) if m2 else None

async def scrap_moneyhouse():
    url = "https://moneyhouse.pe/"
    casa = "MoneyHouse"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": url,
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=25, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text or ""

        compra_raw = _extract_first_span(html, "views-field-field-t-c-compra")
        venta_raw  = _extract_first_span(html, "views-field-field-t-c-venta")

        compra = normalize_rate(_clean_num(compra_raw or "")) if compra_raw else None
        venta  = normalize_rate(_clean_num(venta_raw or "")) if venta_raw else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        estado = "abierto"
        if cerrado:
            estado = "cerrado"
        if compra is None or venta is None:
            estado = "error"

        out = {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": estado,
        }

        if estado == "error":
            out["error"] = "No se pudo extraer compra/venta del HTML (estructura cambió)."

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
