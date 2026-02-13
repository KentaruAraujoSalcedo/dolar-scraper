import re
import asyncio
import httpx
from scrapers.utils import normalize_rate


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
def _snippet(s: str, n=600) -> str:
    return (s or "").replace("\r", "").replace("\n", " ")[:n]

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

        # 1) entrar al home para sembrar cookies
        await page.goto("https://www.cambiomundial.com/", wait_until="domcontentloaded", timeout=45000)

        # 2) ir al endpoint real
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)

        # 3) esperar explícitamente a los elementos (clave)
        try:
            await page.wait_for_selector(
                "label#lblValorCompra, input#txtValorCompra",
                timeout=20000
            )
        except Exception:
            # igual devolvemos el HTML para debug
            html = await page.content()
            await browser.close()
            raise RuntimeError(f"Playwright: no apareció selector de compra. snip={_snippet(html)}")

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
    # 1️⃣ Intento con httpx (rápido)
    # =========
    try:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True
        ) as client:

            # Warm-up cookies (1 sola vez)
            await client.get(url)

            # Solo 1 intento real (no queremos perder tiempo)
            r = await client.get(endpoint)
            r.raise_for_status()

            html = r.text or ""
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
    # 2️⃣ Fallback Playwright
    # =========
    try:
        html2 = await _fetch_html_playwright(endpoint)
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
