import httpx
import re
from scrapers.utils import normalize_rate

def _clean(txt: str) -> str:
    return re.sub(r"[^\d.,]", "", (txt or "")).replace(",", ".")

async def scrap_yanki():
    casa = "yanki"
    url = "https://yanki.pe"
    endpoint = "https://apis.yanki.pe/api/yanki/v1/tipos-cambio"
    params = {"search": "estado:actual"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Origin": "https://yanki.pe",
        "Referer": "https://yanki.pe/",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint, params=params)
            r.raise_for_status()
            data = r.json()

        # Esperado: {"success": true, "data": [ { tc_compra, tc_venta, ... } ]}
        rows = (data or {}).get("data") if isinstance(data, dict) else None
        if not rows:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error": "Respuesta inesperada: no vino data[]",
            }

        item = rows[0]
        compra_raw = item.get("tc_compra")
        venta_raw  = item.get("tc_venta")

        compra = normalize_rate(_clean(compra_raw)) if compra_raw else None
        venta  = normalize_rate(_clean(venta_raw)) if venta_raw else None

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
