# scrapers/rextie.py
import re
from playwright.async_api import async_playwright

def _extract_rate(text: str):
    # Agarra el primer número tipo 3.3385
    m = re.search(r"\d+\.\d+", text or "")
    return float(m.group(0)) if m else None

async def scrap_rextie():
    url = "https://www.rextie.com/"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # Espera a que exista el webcomponent
            await page.wait_for_selector("fx-rates", timeout=30000)

            # Espera a que deje de estar en loading dentro del shadow DOM
            # (Playwright puede “atravesar” open shadow DOM con CSS normal)
            await page.wait_for_selector("fx-rates div.container[aria-busy='false']", timeout=30000)

            # Lee aria-label (más estable que texto visual)
            buy_tab  = page.locator("fx-rates a[role='tab'][aria-label^='Comprar dólares a']").first
            sell_tab = page.locator("fx-rates a[role='tab'][aria-label^='Vender dólares a']").first

            await buy_tab.wait_for(timeout=30000)
            await sell_tab.wait_for(timeout=30000)

            buy_label  = await buy_tab.get_attribute("aria-label")
            sell_label = await sell_tab.get_attribute("aria-label")

            compra = _extract_rate(buy_label)   # “Comprar dólares a X soles” => compra
            venta  = _extract_rate(sell_label)  # “Vender dólares a X soles”  => venta

            # Si todavía está en 3.0000, espera un poco más a que se actualice
            if compra == 3.0 or venta == 3.0 or compra is None or venta is None:
                await page.wait_for_timeout(2500)
                buy_label  = await buy_tab.get_attribute("aria-label")
                sell_label = await sell_tab.get_attribute("aria-label")
                compra = _extract_rate(buy_label)
                venta  = _extract_rate(sell_label)

            if compra is None or venta is None or compra == 3.0 or venta == 3.0:
                raise Exception(f"Valores no válidos aún. buy='{buy_label}' sell='{sell_label}'")

            return {"casa": "Rextie", "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": "Rextie", "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}

    finally:
        if browser:
            await browser.close()
