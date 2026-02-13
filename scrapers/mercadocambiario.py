import httpx
import json
from scrapers.utils import normalize_rate
from playwright.async_api import async_playwright


def _extract_rates(data):
    rates = []
    if isinstance(data, list):
        for block in data:
            if not isinstance(block, dict):
                continue
            for o in block.get("successfulOrders", []) or []:
                if not isinstance(o, dict):
                    continue
                x = o.get("typeExchangeAmount")
                try:
                    p = float(x)
                except Exception:
                    continue
                if 2.8 <= p <= 4.2:
                    rates.append(p)
    return rates


async def _pw_fetch_actives_all(home_url: str, endpoint: str):
    """
    Hace POST al endpoint desde el contexto del navegador (cookies/JS/session).
    Esto puede pasar cuando httpx/curl-cffi reciben 403 en datacenter.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="es-PE",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        # Abre home para que setee cookies / session / cualquier JS
        await page.goto(home_url, wait_until="networkidle", timeout=60000)

        # Ejecuta fetch dentro del navegador
        result = await page.evaluate(
            """async (endpoint) => {
                const res = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: "{}"
                });
                const text = await res.text();
                return { status: res.status, text };
            }""",
            endpoint,
        )

        await browser.close()

    if result["status"] != 200:
        raise RuntimeError(
            f"playwright_fetch_status={result['status']} snip={result['text'][:200]}"
        )

    return json.loads(result["text"])


async def scrap_mercadocambiario():
    casa = "MercadoCambiario"
    url = "https://www.mercadocambiario.pe/"
    endpoint = "https://www.mercadocambiario.pe/api/order/get/actives-all"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Origin": "https://www.mercadocambiario.pe",
        "Referer": "https://www.mercadocambiario.pe/",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    # --- 1) intento httpx (rápido) ---
    try:
        async with httpx.AsyncClient(headers=headers, timeout=25, follow_redirects=True) as client:
            await client.get(url)
            r = await client.post(endpoint, json={})
            if r.status_code == 403:
                raise RuntimeError("blocked_403_httpx")
            r.raise_for_status()
            data = r.json()

        rates = _extract_rates(data)
        if not rates:
            return {
                "casa": casa, "url": url,
                "compra": None, "venta": None,
                "estado": "error",
                "error": "No rates válidos (httpx).",
                "source": "actives-all_httpx",
            }

        return {
            "casa": casa,
            "url": url,
            "compra": normalize_rate(str(max(rates))),
            "venta": normalize_rate(str(min(rates))),
            "estado": "abierto",
            "source": "actives-all_httpx_minmax",
            "n_rates": len(rates),
        }

    except Exception as e_httpx:
        # --- 2) fallback curl-cffi ---
        try:
            from curl_cffi import requests as creq

            creq.get(url, headers=headers, impersonate="chrome120", timeout=25)
            rr = creq.post(endpoint, headers=headers, json={}, impersonate="chrome120", timeout=25)

            if rr.status_code == 403:
                raise RuntimeError("blocked_403_curlcffi")

            if rr.status_code >= 400:
                return {
                    "casa": casa, "url": url,
                    "compra": None, "venta": None,
                    "estado": "error",
                    "error": f"blocked_status={rr.status_code} (curl_cffi). snip={rr.text[:200]}",
                    "source": "actives-all_curlcffi",
                }

            data = rr.json()
            rates = _extract_rates(data)
            if not rates:
                return {
                    "casa": casa, "url": url,
                    "compra": None, "venta": None,
                    "estado": "error",
                    "error": "No rates válidos (curl_cffi).",
                    "source": "actives-all_curlcffi",
                }

            return {
                "casa": casa,
                "url": url,
                "compra": normalize_rate(str(max(rates))),
                "venta": normalize_rate(str(min(rates))),
                "estado": "abierto",
                "source": "actives-all_curlcffi_minmax",
                "n_rates": len(rates),
            }

        except Exception as e_curl:
            # --- 3) fallback Playwright (fetch dentro del navegador) ---
            try:
                data = await _pw_fetch_actives_all(url, endpoint)
                rates = _extract_rates(data)
                if not rates:
                    return {
                        "casa": casa, "url": url,
                        "compra": None, "venta": None,
                        "estado": "error",
                        "error": "No rates válidos (playwright_fetch).",
                        "source": "actives-all_playwright_fetch",
                    }

                return {
                    "casa": casa,
                    "url": url,
                    "compra": normalize_rate(str(max(rates))),
                    "venta": normalize_rate(str(min(rates))),
                    "estado": "abierto",
                    "source": "actives-all_playwright_fetch_minmax",
                    "n_rates": len(rates),
                }

            except Exception as e_pw:
                return {
                    "casa": casa, "url": url,
                    "compra": None, "venta": None,
                    "estado": "error",
                    "error": f"httpx_fail={e_httpx} | curl_cffi_fail={e_curl} | playwright_fail={e_pw}",
                }
