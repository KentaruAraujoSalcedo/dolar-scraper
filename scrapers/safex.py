import os
import json
from scrapers.utils import normalize_rate

# Playwright async
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

DEBUG = os.getenv("DEBUG_SAFEX") == "1"

def _debug_dump(text: str, meta: dict):
    if not DEBUG:
        return
    os.makedirs("data/debug", exist_ok=True)
    with open("data/debug/safex_last.txt", "w", encoding="utf-8") as f:
        f.write(text or "")
    with open("data/debug/safex_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

async def scrap_safex():
    casa = "Safex"
    url = "https://www.safex.pe/"
    endpoint_hint = "cotizacion.php"

    # Si estás en GitHub Actions con xvfb/headless, déjalo en True.
    # Si quieres ver el navegador localmente, pon SAFEX_HEADLESS=0
    headless = os.getenv("SAFEX_HEADLESS", "1") != "0"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                locale="es-PE",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            captured_json = None
            captured_text = None
            captured_url = None
            captured_status = None

            async def on_response(resp):
                nonlocal captured_json, captured_text, captured_url, captured_status
                try:
                    u = resp.url or ""
                    if endpoint_hint in u:
                        captured_url = u
                        captured_status = resp.status
                        # intenta leer como json
                        try:
                            captured_json = await resp.json()
                        except Exception:
                            captured_text = await resp.text()
                except Exception:
                    pass

            page.on("response", on_response)

            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Espera un poco a que se dispare el request del endpoint
            # (si existe). No bloquea mucho.
            try:
                # Espera hasta 8s por captura
                for _ in range(16):
                    if captured_json is not None or captured_text is not None:
                        break
                    await page.wait_for_timeout(500)
            except PWTimeout:
                pass

            # 1) Si capturamos JSON del endpoint, parseamos
            if isinstance(captured_json, dict):
                _debug_dump(json.dumps(captured_json, ensure_ascii=False), {
                    "casa": casa,
                    "mode": "captured_json",
                    "captured_url": captured_url,
                    "captured_status": captured_status,
                })

                # Formato esperado: {'response':'success','data':{'precCompra':..., 'precVenta':...}}
                if captured_json.get("response") == "success":
                    data = captured_json.get("data") or {}
                    compra_raw = data.get("precCompra")
                    venta_raw  = data.get("precVenta")

                    compra = normalize_rate(str(compra_raw)) if compra_raw is not None else None
                    venta  = normalize_rate(str(venta_raw)) if venta_raw is not None else None

                    if compra is not None and venta is not None:
                        cerrado = (compra == 0.0 and venta == 0.0)
                        await browser.close()
                        return {
                            "casa": casa,
                            "url": url,
                            "compra": compra,
                            "venta": venta,
                            "estado": "cerrado" if cerrado else "abierto",
                            "source": "playwright",
                        }

                # Si no fue success, igual lo reportamos con detalle
                await browser.close()
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error_type": "api_unexpected",
                    "source": "playwright",
                    "error": f"Endpoint respondió JSON inesperado. status={captured_status} payload={captured_json!r}",
                }

            # 2) Si capturamos texto (no JSON), lo guardamos como evidencia
            if captured_text:
                _debug_dump(captured_text, {
                    "casa": casa,
                    "mode": "captured_text",
                    "captured_url": captured_url,
                    "captured_status": captured_status,
                })

            # 3) Fallback DOM (por si el endpoint no existe o cambió)
            # Intenta encontrar números cerca de "Compra" y "Venta" en la página.
            # (Los selectores exactos dependen del DOM; esto es fallback suave.)
            content = await page.content()
            _debug_dump(content[:2000], {"casa": casa, "mode": "dom_fallback_snip"})

            # Busca en el contenido completo con regex simple
            import re
            buy_m = re.search(r"compra.{0,120}?(\d[.,]\d{2,4})", content, re.IGNORECASE | re.DOTALL)
            sel_m = re.search(r"venta.{0,120}?(\d[.,]\d{2,4})",  content, re.IGNORECASE | re.DOTALL)

            buy = buy_m.group(1) if buy_m else None
            sel = sel_m.group(1) if sel_m else None

            compra = normalize_rate(str(buy).replace(",", ".")) if buy else None
            venta  = normalize_rate(str(sel).replace(",", ".")) if sel else None

            await browser.close()

            if compra is not None and venta is not None:
                cerrado = (compra == 0.0 and venta == 0.0)
                return {
                    "casa": casa,
                    "url": url,
                    "compra": compra,
                    "venta": venta,
                    "estado": "cerrado" if cerrado else "abierto",
                    "source": "playwright_dom",
                }

            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "error_type": "parse_error",
                "source": "playwright",
                "error": "No se pudo capturar cotizacion.php ni extraer compra/venta del DOM.",
            }

    except Exception as e:
        _debug_dump("", {
            "casa": casa,
            "mode": "exception",
            "exception_type": type(e).__name__,
            "exception_message": str(e),
        })
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error_type": "error",
            "exception_type": type(e).__name__,
            "exception_message": str(e),
            "error": f"No se pudo scrapear (playwright): {e}",
        }
