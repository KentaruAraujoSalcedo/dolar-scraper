# scrapers/global66.py
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

QUOTE_URL = (
    "https://api.global66.com/quote/public"
    "?originRoute=227&destinationRoute=59"
    "&amount=1000&way=origin&paymentType=WIRE_TRANSFER"
)

async def scrap_global66():
    url = "https://www.global66.com/pe/envios-de-dinero/"
    casa = "Global66"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(locale="es-PE", timezone_id="America/Lima")

            resp = await context.request.get(QUOTE_URL, timeout=60000)
            data = await resp.json()

            await browser.close()

            q = (data or {}).get("quoteData") or {}
            origin_amt = q.get("originAmount")          # PEN
            dest_amt   = q.get("destinationAmount")     # USD

            if not origin_amt or not dest_amt:
                raise ValueError(f"Respuesta inesperada: originAmount={origin_amt}, destinationAmount={dest_amt}")

            # 1 USD = (PEN / USD)
            rate = float(origin_amt) / float(dest_amt)

            # normaliza a tu formato (y evita problemas de coma)
            rate = normalize_rate(str(rate))

            if rate is None:
                raise ValueError("No se pudo normalizar el rate")

            return {
                "casa": casa,
                "url": url,
                "compra": rate,
                "venta": rate
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "error": f"No se pudo scrapear: {e}"
        }
