# scrapers/kallpacambios.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate


async def scrap_kallpacambios():
    url = "https://kallpacambios.com/"
    casa = "KallpaCambios"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # 1) Esperar a que exista el bloque
            await page.locator("h3, p", has_text="Tipo de cambio").first.wait_for(timeout=25000)

            # 2) Esperar a que aparezcan 2 valores > 3.1 (compra y venta reales)
            await page.wait_for_function(
                """
                () => {
                    const nodes = Array.from(document.querySelectorAll("font, p"));
                    const texts = nodes.map(n => (n.innerText || "").trim()).filter(Boolean);

                    const nums = texts
                      .map(t => t.replace(",", ".").match(/S\\/?\\s*\\.?([0-9]+(?:\\.[0-9]+)?)/))
                      .filter(Boolean)
                      .map(m => parseFloat(m[1]))
                      .filter(n => !isNaN(n) && n > 3.1);

                    return nums.length >= 2;
                }
                """,
                timeout=25000,
            )

            # 3) Extraer ya con los valores cargados
            textos = []
            textos += await page.locator("font").all_text_contents()
            textos += await page.locator("p").all_text_contents()

            valores = []
            for t in textos:
                t = t.replace(",", ".")
                m = re.search(r"S/?\s*\.?([0-9]+(?:\.[0-9]+)?)", t)
                if m:
                    v = normalize_rate(m.group(1))
                    if v and v > 3.1:
                        valores.append(v)

            # Quitar duplicados preservando orden (a veces sale repetido)
            uniq = []
            for v in valores:
                if v not in uniq:
                    uniq.append(v)

            compra = uniq[0] if len(uniq) > 0 else None
            venta = uniq[1] if len(uniq) > 1 else None

            return {"casa": casa, "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": casa, "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}

    finally:
        if browser:
            await browser.close()
