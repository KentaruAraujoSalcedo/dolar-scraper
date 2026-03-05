import httpx
from scrapers.utils import normalize_rate

async def scrap_cambiosmass():
    casa = "cambiosmass"
    url = "https://cambiosmass.com/"
    endpoint = "https://cambiosmass.com/api/rates-history"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint)
            r.raise_for_status()
            data = r.json()

        current = (data or {}).get("current") or {}
        compra_raw = current.get("compra")
        venta_raw  = current.get("venta")

        compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
        venta  = normalize_rate(str(venta_raw)) if venta_raw is not None else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        out = {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": "cerrado" if cerrado else "abierto",
        }

        # opcional: guardar timestamp si lo quieres
        updated_at = current.get("updatedAt")
        if updated_at:
            out["updatedAt"] = updated_at

        # si no encontró tasas, marca error (mejor que “abierto” sin data)
        if compra is None or venta is None:
            out["estado"] = "error"
            out["error"] = "No se encontró 'current.compra/venta' en la respuesta."

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
