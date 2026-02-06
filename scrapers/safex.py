# scrapers/safex.py
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate
import re

async def scrap_safex():
    url = "https://www.safex.pe/"
    casa = "Safex"
    browser = None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)

            # Espera a que aparezcan los elementos con tasas
            await page.wait_for_selector(".calc-tc-valor", timeout=15000)

            # Extrae textos candidatos (pueden venir con símbolos o espacios)
            textos = await page.locator(".calc-tc-valor").all_text_contents()

            # Limpia a "3.567" (acepta comas, puntos, "S/ ", etc.)
            def _clean(x: str) -> str:
                return re.sub(r"[^\d.,]", "", (x or "")).replace(",", ".")

            valores = [_clean(t) for t in textos if _clean(t)]
            # A veces Safex muestra primero venta y luego compra (según el layout),
            # pero si el orden no es claro, mejor intenta identificar por posición y validar.
            # Mantendremos la misma lógica: ventas[0], compras[1] y normalizamos.

            venta  = normalize_rate(valores[0]) if len(valores) > 0 else None
            compra = normalize_rate(valores[1]) if len(valores) > 1 else None

            return {
                "casa": casa,
                "url": url,
                "compra": compra,  # None si 0 / inválido
                "venta":  venta,   # None si 0 / inválido
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "error": f"No se pudo scrapear: {e}",
        }
    finally:
        if browser:
            await browser.close()
