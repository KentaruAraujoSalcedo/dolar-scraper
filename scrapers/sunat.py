from playwright.async_api import async_playwright
from datetime import date
import re

async def scrap_sunat():
    url = "https://www.sunat.gob.pe/cl-at-ittipcam/tcS01Alias"
    base = {"casa": "SUNAT", "url": url}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("td[data-date]", timeout=60000)

            hoy = date.today().isoformat()

            # ✅ MÁS ROBUSTO: no dependemos del "T05:00:00.000Z"
            celda = page.locator(f'td[data-date^="{hoy}"]').first
            if await celda.count() == 0:
                await browser.close()
                return {**base, "error": f"No se encontró celda para hoy ({hoy})"}

            textos = (await celda.inner_text()).strip()

            # Intento normal
            compra = re.search(r"Compra\s+\"?\s*([\d.]+)", textos, re.IGNORECASE)
            venta = re.search(r"Venta\s+\"?\s*([\d.]+)", textos, re.IGNORECASE)

            # Si no encontró, intenta capturar 2 números del texto como fallback
            if not (compra and venta):
                nums = re.findall(r"(\d+\.\d+)", textos)
                if len(nums) >= 2:
                    return {**base, "compra": float(nums[0]), "venta": float(nums[1])}

                await browser.close()
                return {**base, "error": f"No se pudo extraer compra/venta. Texto: {textos[:200]}"}

            data = {
                **base,
                "compra": float(compra.group(1)),
                "venta": float(venta.group(1)),
            }

            await browser.close()
            return data

    except Exception as e:
        return {**base, "error": str(e)}
