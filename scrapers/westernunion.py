import httpx
from scrapers.utils import normalize_rate

async def scrap_westernunion():
    casa = "WesternUnion"
    url = "https://www.westernunionperu.pe/cambiodemoneda"
    endpoint = "https://www.westernunionperu.pe/cambiodemoneda/Operation/PostTipoCambio"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.westernunionperu.pe",
        "Referer": url,
        "X-Requested-With": "XMLHttpRequest",
    }

    # A veces estos endpoints esperan POST aunque no mandes body.
    # Mandamos JSON vacío para ser compatibles.
    payload = {}

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.post(endpoint, json=payload)
            r.raise_for_status()
            data = r.json()

        # Selección de tasas:
        # Preferimos DT_* (digital) y hacemos fallback a TC_*
        compra_raw = data.get("DT_Compra") if isinstance(data, dict) else None
        venta_raw  = data.get("DT_Venta") if isinstance(data, dict) else None

        if compra_raw is None or venta_raw is None:
            compra_raw = (data.get("TC_Compra") if isinstance(data, dict) else None)
            venta_raw  = (data.get("TC_Venta") if isinstance(data, dict) else None)

        compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
        venta  = normalize_rate(str(venta_raw)) if venta_raw is not None else None

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
