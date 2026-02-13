import re
import asyncio
import httpx
from scrapers.utils import normalize_rate

# --- extractores ---
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

def _snippet(s: str, n=500) -> str:
    return (s or "").replace("\r", "").replace("\n", " ")[:n]

def _looks_blocked(html: str) -> bool:
    h = (html or "").lower()
    return any(x in h for x in [
        "access denied", "request blocked", "captcha", "attention required",
        "cloudflare", "pardon the interruption", "/cdn-cgi/", "suspicious activity"
    ])

async def _get_with_retries(client: httpx.AsyncClient, url: str, tries=4) -> httpx.Response:
    last = None
    for i in range(tries):
        try:
            r = await client.get(url)
            if r.status_code in (429, 500, 502, 503, 504):
                await asyncio.sleep(1.0 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
            last = e
            await asyncio.sleep(1.0 * (i + 1))
    raise last or RuntimeError("GET failed after retries")

def _parse_rates(html: str):
    compra_raw = _extract_by_label_id(html, "lblValorCompra") or _extract_by_input_id(html, "txtValorCompra")
    venta_raw  = _extract_by_label_id(html, "lblValorVenta")  or _extract_by_input_id(html, "txtValorVenta")
    compra = normalize_rate(compra_raw) if compra_raw else None
    venta  = normalize_rate(venta_raw) if venta_raw else None
    return compra, venta

async def _fetch_html_playwright(target_url: str) -> str:
    # Import local para no forzar Playwright cuando no se necesita
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="es-PE",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        await page.goto(target_url, wait_until="networkidle", timeout=45000)
        html = await page.content()
        await browser.close()
        return html

async def scrap_cambiomundial():
    casa = "CambioMundial"
    url = "https://www.cambiomundial.com/"
    endpoint = "https://www.cambiomundial.com/appcm/tpc/tipocambio/index"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": url,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    timeout = httpx.Timeout(30.0, connect=10.0)

    # 1) intento httpx
    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
            await _get_with_retries(client, url, tries=2)      # warm-up cookies
            r = await _get_with_retries(client, endpoint, tries=4)
            html = r.text or ""
            compra, venta = _parse_rates(html)

            if compra and venta:
                return {"casa": casa, "url": url, "compra": compra, "venta": venta, "estado": "abierto", "source": "httpx"}

            # si parece bloqueo o no hay IDs => fallback
            blocked = _looks_blocked(html)
            if blocked or (compra is None and venta is None):
                raise RuntimeError(f"httpx_no_parse blocked={blocked} ct={(r.headers.get('content-type') or '')} snip={_snippet(html)}")

    except Exception as e_httpx:
        # 2) fallback Playwright
        try:
            html2 = await _fetch_html_playwright(endpoint)
            compra2, venta2 = _parse_rates(html2)
            if compra2 and venta2:
                return {"casa": casa, "url": url, "compra": compra2, "venta": venta2, "estado": "abierto", "source": "playwright"}

            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "source": "playwright",
                "error": f"No se pudo extraer IDs. snip={_snippet(html2)} | prev={e_httpx}",
            }
        except Exception as e_pw:
            return {
                "casa": casa,
                "url": url,
                "compra": None,
                "venta": None,
                "estado": "error",
                "source": "playwright",
                "error": f"Fallback Playwright falló: {e_pw} | prev={e_httpx}",
            }
