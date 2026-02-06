# scrapers/moneyplus.py
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

API_LAST = "https://moneyplus.pseperu.pro/api/exchange-rates/last-exchange-rate"

async def scrap_moneyplus():
    url = "https://www.moneyplus.pe/"
    casa = "MoneyPlus"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                locale="es-PE",
                timezone_id="America/Lima",
            )

            resp = await context.request.get(API_LAST, timeout=60000)
            data = await resp.json()

            await browser.close()

            compra_raw = data.get("priceCompra")
            venta_raw  = data.get("priceVenta")

            compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
            venta  = normalize_rate(str(venta_raw))  if venta_raw  is not None else None

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
