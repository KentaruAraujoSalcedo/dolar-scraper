import re
import httpx
from bs4 import BeautifulSoup
from scrapers.utils import normalize_rate

def _clean(txt: str) -> str:
    return re.sub(r"[^\d.,]", "", (txt or "")).replace(",", ".")

async def scrap_xcambio():
    url = "https://x-cambio.com/"
    casa = "xcambio"

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

        soup = BeautifulSoup(html, "html.parser")

        # Mejor fuente: atributos data-*
        cambio = soup.select_one("#cambio")
        compra_raw = cambio.get("data-compra") if cambio else None
        venta_raw  = cambio.get("data-venta") if cambio else None

        # Fallback: spans visibles
        if not compra_raw:
            el = soup.select_one("#cambio-compra")
            compra_raw = el.get_text(strip=True) if el else None
        if not venta_raw:
            el = soup.select_one("#cambio-venta")
            venta_raw = el.get_text(strip=True) if el else None

        compra = normalize_rate(_clean(compra_raw)) if compra_raw else None
        venta  = normalize_rate(_clean(venta_raw)) if venta_raw else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        # Si no encontró, lo marcamos error (mejor que inventar)
        if compra is None or venta is None:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "No se encontraron data-compra/data-venta ni #cambio-compra/#cambio-venta en el HTML.",
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
