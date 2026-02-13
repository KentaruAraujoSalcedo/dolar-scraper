import os
import re
from datetime import datetime

import httpx
from scrapers.utils import normalize_rate

# acepta 2-4 decimales: 3.34 / 3.363 / 3.345 / 3,35
RATE_RE = re.compile(r"\b\d[.,]\d{2,4}\b", re.I)

# Busca número cerca de "Compra" y "Venta"
BUY_CTX_RE  = re.compile(r"compra[^0-9]{0,80}(\d[.,]\d{2,4})", re.I | re.S)
SELL_CTX_RE = re.compile(r"venta[^0-9]{0,80}(\d[.,]\d{2,4})", re.I | re.S)

def _to_float(s: str):
    s = re.sub(r"[^\d.,]", "", (s or "")).strip()
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def _dump_debug(name: str, content: str) -> str:
    os.makedirs("debug_html", exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"debug_html/{name.lower()}_{ts}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content or "")
    return path

def _extract_buy_sell_from_html_by_context(html: str):
    h = html or ""

    mb = BUY_CTX_RE.search(h)
    ms = SELL_CTX_RE.search(h)

    buy  = _to_float(mb.group(1)) if mb else None
    sell = _to_float(ms.group(1)) if ms else None

    if buy is not None and sell is not None:
        b, s = (buy, sell) if buy <= sell else (sell, buy)
        # spread razonable
        if (s - b) <= 0.30 and (2.8 <= b <= 4.2) and (2.8 <= s <= 4.2):
            return b, s

    return None, None

def _extract_buy_sell_fallback_numbers(html: str):
    """Plan B: si no hay Compra/Venta claro, agarra dos números en rango PEN/USD."""
    nums = []
    for m in RATE_RE.finditer(html or ""):
        x = _to_float(m.group(0))
        if x is None:
            continue
        # rango realista para PEN/USD
        if 2.8 <= x <= 4.2:
            nums.append(x)

    # dedupe manteniendo orden
    uniq = []
    for x in nums:
        if x not in uniq:
            uniq.append(x)

    if len(uniq) >= 2:
        b, s = (uniq[0], uniq[1]) if uniq[0] <= uniq[1] else (uniq[1], uniq[0])
        if (s - b) <= 0.30:
            return b, s

    return None, None

def _extract_rates_from_drupal_payload(payload):
    """payload: lista drupal_ajax con comandos insert. Extrae insert_html y parsea."""
    insert_html = None
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("command") == "insert":
                insert_html = item.get("data") or ""
                break

    if not insert_html:
        return None, None, None  # buy, sell, insert_html

    # 1) intento por contexto Compra/Venta (lo más confiable)
    buy, sell = _extract_buy_sell_from_html_by_context(insert_html)
    if buy is not None and sell is not None:
        return buy, sell, insert_html

    # 2) fallback por números en rango
    buy, sell = _extract_buy_sell_fallback_numbers(insert_html)
    return buy, sell, insert_html


async def scrap_misterdollar():
    casa = "MisterDollar"
    url = "https://misterdollar.pe/"

    endpoint = "https://misterdollar.pe/views/ajax"
    params = {
        "_wrapper_format": "drupal_ajax",
        "view_name": "view_block_tasaactual",
        "view_display_id": "block_1",
        "view_args": "",
        "view_path": "/front",
        "view_base_path": "",
        "pager_element": "0",
        "_drupal_ajax": "1",
        "ajax_page_state[theme]": "tema",
        "ajax_page_state[theme_token]": "",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint, params=params)

            buy = sell = None
            insert_html = None

            if r.status_code < 400:
                payload = r.json()
                buy, sell, insert_html = _extract_rates_from_drupal_payload(payload)

            # Si AJAX falló o no pudo parsear, intenta home HTML
            if buy is None or sell is None:
                home = await client.get(url)
                home.raise_for_status()
                html = home.text or ""

                buy2, sell2 = _extract_buy_sell_from_html_by_context(html)
                if buy2 is None or sell2 is None:
                    buy2, sell2 = _extract_buy_sell_fallback_numbers(html)

                buy, sell = buy2, sell2

                if buy is None or sell is None:
                    path = _dump_debug("misterdollar_home", html)
                    return {
                        "casa": casa,
                        "url": url,
                        "compra": None,
                        "venta": None,
                        "estado": "error",
                        "error": f"No se pudo identificar compra/venta en HOME. Debug: {path}",
                    }

            compra = normalize_rate(str(buy)) if buy is not None else None
            venta  = normalize_rate(str(sell)) if sell is not None else None

            # Si sigue raro, dump del insert_html para inspección
            if (compra is None or venta is None) and insert_html:
                path = _dump_debug("misterdollar_insert", insert_html)
                return {
                    "casa": casa,
                    "url": url,
                    "compra": compra,
                    "venta": venta,
                    "estado": "error",
                    "error": f"No se pudo identificar compra/venta en INSERT. Debug: {path}",
                }

            # guardrails finales (evita outliers)
            if compra is not None and venta is not None:
                if not (3.0 <= compra <= 3.7 and 3.0 <= venta <= 3.7 and venta >= compra):
                    # dump para revisar por qué salió raro
                    if insert_html:
                        path = _dump_debug("misterdollar_outlier_insert", insert_html)
                    else:
                        path = "N/A"
                    return {
                        "casa": casa,
                        "url": url,
                        "compra": None,
                        "venta": None,
                        "estado": "error",
                        "error": f"Outlier detectado compra={compra} venta={venta}. Debug: {path}",
                    }

            cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
                "estado": "cerrado" if cerrado else "abierto",
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
