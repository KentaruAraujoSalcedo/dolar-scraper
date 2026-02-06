# scrapers/acomo.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

async def scrap_acomo():
    url = "https://acomo.com.pe/"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            bid = page.locator("#current_bid")
            off = page.locator("#current_offer")

            # Espera a que existan
            await bid.wait_for(state="visible", timeout=20000)
            await off.wait_for(state="visible", timeout=20000)

            # Espera a que AMBOS tengan dígitos (valor ya “hydrated”)
            await page.wait_for_function(
                """() => {
                    const b = document.querySelector('#current_bid')?.innerText || '';
                    const o = document.querySelector('#current_offer')?.innerText || '';
                    return /\\d/.test(b) && /\\d/.test(o);
                }""",
                timeout=20000
            )

            compra_text = (await bid.text_content() or "").strip()
            venta_text  = (await off.text_content() or "").strip()

            compra = normalize_rate(compra_text.replace("S/", "").replace("s/", ""))
            venta  = normalize_rate(venta_text.replace("S/", "").replace("s/", ""))

            return {"casa": "Acomo", "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": "Acomo", "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}

    finally:
        if browser:
            await browser.close()
