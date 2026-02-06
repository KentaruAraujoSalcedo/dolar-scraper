# scrapers/dinekash.py
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

API_COMPRA = "https://api.dinekash.pe/cotizacion/buscar/USDPEN"
API_VENTA  = "https://api.dinekash.pe/cotizacion/buscar/PENUSD"

async def scrap_dinekash():
    url = "https://dinekash.pe/"
    casa = "DineKash"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                locale="es-PE",
                timezone_id="America/Lima",
            )

            r_compra = await context.request.get(API_COMPRA)
            j_compra = await r_compra.json()
            compra_raw = j_compra.get("cotizacion", [{}])[0].get("cotizacion")

            r_venta = await context.request.get(API_VENTA)
            j_venta = await r_venta.json()
            venta_raw = j_venta.get("cotizacion", [{}])[0].get("cotizacion")

            await browser.close()

            compra = normalize_rate(compra_raw)
            venta  = normalize_rate(venta_raw)

            if compra is None or venta is None:
                raise ValueError(f"Valores inválidos compra={compra_raw}, venta={venta_raw}")

            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "error": f"No se pudo scrapear: {e}"
        }
