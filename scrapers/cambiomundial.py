import re
import httpx
from scrapers.utils import normalize_rate

def _extract_by_label_id(html: str, label_id: str) -> str | None:
    # Ej: <label id='lblValorCompra'>3.350</label>
    m = re.search(rf"id=['\"]{re.escape(label_id)}['\"][^>]*>\s*([0-9]+[.,][0-9]{{3,4}})\s*<", html, re.I)
    return m.group(1) if m else None

def _extract_by_input_id(html: str, input_id: str) -> str | None:
    # Ej: <input ... id="txtValorCompra" value="3.3500" />
    m = re.search(rf"id=['\"]{re.escape(input_id)}['\"][^>]*value=['\"]\s*([0-9]+[.,][0-9]{{3,6}})\s*['\"]", html, re.I)
    return m.group(1) if m else None

async def scrap_cambiomundial():
    casa = "CambioMundial"
    url = "https://www.cambiomundial.com/"
    endpoint = "https://www.cambiomundial.com/appcm/tpc/tipocambio/index"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,*/*",
        "Referer": url,
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=25, follow_redirects=True) as client:
            r = await client.get(endpoint)
            r.raise_for_status()
            html = r.text or ""

        compra_raw = _extract_by_label_id(html, "lblValorCompra") or _extract_by_input_id(html, "txtValorCompra")
        venta_raw  = _extract_by_label_id(html, "lblValorVenta")  or _extract_by_input_id(html, "txtValorVenta")

        compra = normalize_rate(compra_raw) if compra_raw else None
        venta  = normalize_rate(venta_raw) if venta_raw else None

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
            out["error"] = "No se pudo extraer compra/venta (IDs no encontrados o HTML cambió)."

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
