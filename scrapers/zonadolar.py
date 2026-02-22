import httpx
from scrapers.utils import normalize_rate

async def scrap_zonadolar():
    casa = "zonadolar"
    url = "https://zonadolar.pe/"
    endpoint = "https://zonadolar.pe/currencies"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
        "Origin": url,
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20) as client:
            r = await client.get(endpoint)
            r.raise_for_status()
            data = r.json()

        if not isinstance(data, list) or len(data) < 2:
            raise ValueError("Respuesta inesperada")

        # buscar USD y PEN
        usd = next((x for x in data if x.get("iso") == "USD"), None)
        pen = next((x for x in data if x.get("iso") == "PEN"), None)

        if not usd or not pen:
            raise ValueError("No se encontraron USD/PEN")

        venta_raw = usd.get("rate")
        compra_raw = pen.get("rate")

        compra = normalize_rate(str(compra_raw))
        venta = normalize_rate(str(venta_raw))

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
