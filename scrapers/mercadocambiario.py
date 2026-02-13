import httpx
from scrapers.utils import normalize_rate

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
            await client.get(url)  # warmup cookies
            r = await client.post(endpoint, json={})

            # si es 403, pasamos a fallback sin romper todo el run
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

        venta_raw = min(rates)
        compra_raw = max(rates)

        return {
            "casa": casa,
            "url": url,
            "compra": normalize_rate(str(compra_raw)),
            "venta": normalize_rate(str(venta_raw)),
            "estado": "abierto",
            "source": "actives-all_httpx_minmax",
            "n_rates": len(rates),
        }

    except Exception as e_httpx:
        # --- 2) fallback curl-cffi (mejor fingerprint TLS / pasa datacenter) ---
        try:
            from curl_cffi import requests as creq

            creq.get(url, headers=headers, impersonate="chrome120", timeout=25)
            rr = creq.post(endpoint, headers=headers, json={}, impersonate="chrome120", timeout=25)

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

            venta_raw = min(rates)
            compra_raw = max(rates)

            return {
                "casa": casa,
                "url": url,
                "compra": normalize_rate(str(compra_raw)),
                "venta": normalize_rate(str(venta_raw)),
                "estado": "abierto",
                "source": "actives-all_curlcffi_minmax",
                "n_rates": len(rates),
            }

        except Exception as e2:
            return {
                "casa": casa, "url": url,
                "compra": None, "venta": None,
                "estado": "error",
                "error": f"httpx_fail={e_httpx} | curl_cffi_fail={e2}",
            }
