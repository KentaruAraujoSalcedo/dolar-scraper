# scrapers/kambista.py
import re
from playwright.async_api import async_playwright

def _to_float(s: str) -> float:
    s = s.strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    return float(s)

async def scrap_kambista():
    url = "https://kambista.com/"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 👈 True en producción
        page = await browser.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Espera a que los números aparezcan (hydration)
        await page.wait_for_function(
            """() => {
                const c = document.querySelector('label[for="USD"]')?.innerText || '';
                const v = document.querySelector('label[for="PEN"]')?.innerText || '';
                return /Compra:\\s*[0-9]/.test(c) && /Venta:\\s*[0-9]/.test(v);
            }""",
            timeout=20000
        )

        compra_txt = await page.locator('label[for="USD"]').text_content()
        venta_txt  = await page.locator('label[for="PEN"]').text_content()

        await browser.close()

        compra = _to_float(re.search(r"Compra:\s*([0-9.,]+)", compra_txt).group(1))
        venta  = _to_float(re.search(r"Venta:\s*([0-9.,]+)", venta_txt).group(1))

        return {
            "casa": "Kambista",
            "url": url,
            "compra": compra,
            "venta": venta
        }
