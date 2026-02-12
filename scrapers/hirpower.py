import httpx
from scrapers.utils import normalize_rate

async def scrap_hirpower():
    casa = "Hirpower"
    url = "https://hirpower.com/"
    endpoint = "https://www.hirpower.com/config/getconfig"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.hirpower.com/",
        "Origin": "https://www.hirpower.com",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint)
            r.raise_for_status()
            data = r.json()

        cfg = (data or {}).get("config") or {}

        # Campos típicos según tu preview (pueden variar)
        # - base: a veces es compra o un "base" usado para cálculo
        # - compra/venta pueden venir como: config_tipocambio_compra / config_tipocambio_venta
        compra_raw = (
            cfg.get("config_tipocambio_compra")
            or cfg.get("config_tipocambio_buy")
            or cfg.get("config_tc_compra")
            or cfg.get("config_compra")
        )
        venta_raw = (
            cfg.get("config_tipocambio_venta")
            or cfg.get("config_tipocambio_sale")
            or cfg.get("config_tc_venta")
            or cfg.get("config_venta")
        )

        base_raw = cfg.get("config_tipocambio_base")

        compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
        venta  = normalize_rate(str(venta_raw)) if venta_raw is not None else None

        # Fallback: si no vienen compra/venta, al menos usa base para ambos (mejor que nada)
        if (compra is None or venta is None) and base_raw is not None:
            base = normalize_rate(str(base_raw))
            # si solo hay base, lo ponemos como venta y compra igual (o ambos base)
            compra = compra if compra is not None else base
            venta  = venta  if venta  is not None else base

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        if compra is None or venta is None:
            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
                "estado": "error",
                "error": "No se encontraron campos compra/venta en config (estructura cambió).",
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
