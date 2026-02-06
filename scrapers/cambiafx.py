# scrapers/cambiafx.py
import re
from pathlib import Path
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate


def _extract_last_number(text: str):
    if not text:
        return None
    matches = re.findall(r"\d+[.,]\d+", text)
    return matches[-1] if matches else None


async def scrap_cambiafx():
    url = "https://cambiafx.pe/"
    casa = "CambiaFX"
    browser = None
    page = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )

            # ✅ En Actions ayuda fijar viewport/UA/locale para que cargue igual
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="es-PE",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            page = await context.new_page()

            # ✅ networkidle suele ser más estable en sitios JS
            await page.goto(url, timeout=90000, wait_until="networkidle")

            # (Opcional) cookies
            try:
                await page.get_by_role("button", name=re.compile("ACEPTAR", re.I)).click(timeout=2500)
            except Exception:
                pass

            buy_btn = page.locator('button[aria-label*="compra de dólares" i]').first
            sell_btn = page.locator('button[aria-label*="venta de dólares" i]').first

            await buy_btn.wait_for(state="visible", timeout=30000)
            await sell_btn.wait_for(state="visible", timeout=30000)

            # ✅ Espera a que el texto tenga un número real
            await page.wait_for_function(
                """() => {
                    const buy = document.querySelector('button[aria-label*="compra de dólares" i]');
                    const sell = document.querySelector('button[aria-label*="venta de dólares" i]');
                    if (!buy || !sell) return false;
                    const t1 = buy.innerText || buy.getAttribute("aria-label") || "";
                    const t2 = sell.innerText || sell.getAttribute("aria-label") || "";
                    return /\\d+[.,]\\d+/.test(t1) && /\\d+[.,]\\d+/.test(t2);
                }""",
                timeout=30000
            )

            compra_raw = (await buy_btn.inner_text()).strip()
            venta_raw = (await sell_btn.inner_text()).strip()

            compra_num = _extract_last_number(compra_raw)
            venta_num = _extract_last_number(venta_raw)

            compra = normalize_rate(compra_num) if compra_num else None
            venta = normalize_rate(venta_num) if venta_num else None

            return {"casa": casa, "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        # ✅ DEBUG: guarda evidencia cuando falle
        try:
            os_dir = Path("data")
            os_dir.mkdir(parents=True, exist_ok=True)
            if page:
                await page.screenshot(path="data/cambiafx_error.png", full_page=True)
                Path("data/cambiafx_error.html").write_text(await page.content(), encoding="utf-8")
        except Exception:
            pass

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
