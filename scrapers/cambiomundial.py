import re
import httpx
from scrapers.utils import normalize_rate


# -------------------------
# Helpers
# -------------------------
def _snippet(s: str, n=600) -> str:
    return (s or "").replace("\r", "").replace("\n", " ")[:n]


def _is_cloudflare_challenge(html: str) -> bool:
    h = (html or "").lower()
    return any(x in h for x in [
        "un momento",               # es-ES
        "just a moment",            # en-US
        "/cdn-cgi/",                # cloudflare challenge path
        "cf-chl-",                  # challenge markers
        "cloudflare",
        "attention required",
        "checking your browser",
        "verify you are human",
        "captcha"
    ])


# -------------------------
# Extractores
# -------------------------
def _extract_by_label_id(html: str, label_id: str) -> str | None:
    m = re.search(
        rf"id=['\"]{re.escape(label_id)}['\"][^>]*>\s*([0-9]+[.,][0-9]{{3,4}})\s*<",
        html, re.I
    )
    return m.group(1) if m else None


def _extract_by_input_id(html: str, input_id: str) -> str | None:
    m = re.search(
        rf"id=['\"]{re.escape(input_id)}['\"][^>]*value=['\"]\s*([0-9]+[.,][0-9]{{3,6}})\s*['\"]",
        html, re.I
    )
    return m.group(1) if m else None


def _parse_rates(html: str):
    compra_raw = (
        _extract_by_label_id(html, "lblValorCompra")
        or _extract_by_input_id(html, "txtValorCompra")
    )
    venta_raw = (
        _extract_by_label_id(html, "lblValorVenta")
        or _extract_by_input_id(html, "txtValorVenta")
    )

    compra = normalize_rate(compra_raw) if compra_raw else None
    venta = normalize_rate(venta_raw) if venta_raw else None
    return compra, venta


# -------------------------
# Playwright fallback
# -------------------------
async def _fetch_html_playwright(target_url: str) -> str:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            locale="es-PE",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # sembrar cookies
        await page.goto("https://www.cambiomundial.com/", wait_until="domcontentloaded", timeout=45000)

        # ir al endpoint
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)

        # esperar contenido real (si no aparece, probablemente challenge)
        try:
            await page.wait_for_selector("label#lblValorCompra, input#txtValorCompra", timeout=20000)
        except Exception:
            html = await page.content()
            await browser.close()
            return html  # devolvemos igual para detectar challenge

        html = await page.content()
        await browser.close()
        return html


# -------------------------
# Scraper principal
# -------------------------
async def scrap_cambiomundial():
    casa = "CambioMundial"
    url = "https://www.cambiomundial.com/"
    endpoint = "https://www.cambiomundial.com/appcm/tpc/tipocambio/index"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "es-PE,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": url,
    }

    timeout = httpx.Timeout(25.0, connect=10.0)

    # =========
    # 1) Intento httpx (rápido)
    # =========
    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
            await client.get(url)  # warm-up cookies

            r = await client.get(endpoint)
            r.raise_for_status()

            html = r.text or ""

            # Cloudflare challenge detectado
            if _is_cloudflare_challenge(html):
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "bloqueado",
                    "source": "cloudflare",
                    "error": f"Cloudflare challenge (httpx). snip={_snippet(html)}",
                }

            compra, venta = _parse_rates(html)
            if compra and venta:
                return {
                    "casa": casa,
                    "url": url,
                    "compra": compra,
                    "venta": venta,
                    "estado": "abierto",
                    "source": "httpx",
                }

    except Exception:
        pass  # Si falla, vamos a Playwright

    # =========
    # 2) Fallback Playwright
    # =========
    try:
        html2 = await _fetch_html_playwright(endpoint)

        # Cloudflare challenge detectado
        if _is_cloudflare_challenge(html2):
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "bloqueado",
                "source": "cloudflare",
                "error": f"Cloudflare challenge (playwright). snip={_snippet(html2)}",
            }

        compra2, venta2 = _parse_rates(html2)
        if compra2 and venta2:
            return {
                "casa": casa,
                "url": url,
                "compra": compra2,
                "venta": venta2,
                "estado": "abierto",
                "source": "playwright",
            }

        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "source": "playwright",
            "error": f"No se pudieron extraer IDs lblValorCompra/lblValorVenta. snip={_snippet(html2)}",
        }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "source": "playwright",
            "error": str(e),
        }
