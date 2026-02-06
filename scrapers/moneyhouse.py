# scrapers/moneyhouse.py
import re
from playwright.async_api import async_playwright
from scrapers.utils import normalize_rate

def _pick_number(s: str):
    if not s:
        return None
    m = re.search(r"\d+[.,]\d+", s)
    return m.group(0) if m else None

async def scrap_moneyhouse():
    url = "https://moneyhouse.pe/"
    casa = "MoneyHouse"
    browser = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            context = await browser.new_context(
                locale="es-PE",
                timezone_id="America/Lima",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )

            page = await context.new_page()

            # En GitHub Actions: networkidle puede colgarse.
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")

            # mini respiro + intento de networkidle sin fallar
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

            # Cerrar cookies si aparece (a veces tapa contenido)
            try:
                await page.get_by_role("button", name=re.compile(r"aceptar", re.I)).click(timeout=3000)
            except Exception:
                pass

            # Espera un contenedor más “general” (menos frágil)
            await page.wait_for_selector(".views-row, .view-content, .principalcontenido", timeout=40000)

            # Extraer por JS de forma ultra tolerante:
            # - prueba varios selectores
            # - si está vacío, intenta leer ::before (por si el valor está como pseudo-elemento)
            data = await page.evaluate(
                """() => {
                    const selectors = [
                      ".views-field-field-t-c-compra span.cant",
                      ".views-field-field-t-c-compra span.cantant",
                      ".views-field-field-t-c-venta span.cant",
                      ".views-field-field-t-c-venta span.cantant",
                    ];

                    const readText = (sel) => {
                      const el = document.querySelector(sel);
                      if (!el) return null;

                      const txt = (el.textContent || "").trim();
                      if (txt) return txt;

                      // fallback: pseudo-elemento ::before
                      try {
                        const b = getComputedStyle(el, "::before").content;
                        if (b && b !== "none") return b.replaceAll('"', '').trim();
                      } catch (e) {}

                      return null;
                    };

                    const compraTxt =
                      readText(".views-field-field-t-c-compra span.cant") ||
                      readText(".views-field-field-t-c-compra span.cantant") ||
                      null;

                    const ventaTxt =
                      readText(".views-field-field-t-c-venta span.cant") ||
                      readText(".views-field-field-t-c-venta span.cantant") ||
                      null;

                    return { compraTxt, ventaTxt };
                }"""
            )

            compra_num = _pick_number(data.get("compraTxt") or "")
            venta_num  = _pick_number(data.get("ventaTxt") or "")

            compra = normalize_rate(compra_num) if compra_num else None
            venta  = normalize_rate(venta_num)  if venta_num else None

            if compra is None or venta is None:
                raise Exception(f"No se encontraron tasas válidas (compraTxt={data.get('compraTxt')}, ventaTxt={data.get('ventaTxt')})")

            return {"casa": casa, "url": url, "compra": compra, "venta": venta}

    except Exception as e:
        return {"casa": casa, "url": url, "compra": None, "venta": None, "error": f"No se pudo scrapear: {e}"}
    finally:
        if browser:
            await browser.close()