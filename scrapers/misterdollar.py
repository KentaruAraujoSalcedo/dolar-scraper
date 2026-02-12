import re
import httpx
from scrapers.utils import normalize_rate

RATE_RE = re.compile(r"\b\d[.,]\d{3,4}\b")

def _to_float_str(s: str) -> str:
    return re.sub(r"[^\d.,]", "", (s or "")).replace(",", ".").strip()

def _extract_rates_from_insert_html(payload) -> tuple[float | None, float | None]:
    """
    payload: lista drupal_ajax con comandos.
    buscamos command=insert y dentro 'data' extraemos tasas.
    """
    insert_html = None
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("command") == "insert":
                insert_html = item.get("data") or ""
                break

    if not insert_html:
        return None, None

    # Extrae tasas razonables del HTML insertado
    nums = []
    for m in RATE_RE.finditer(insert_html):
        raw = m.group(0)
        try:
            x = float(_to_float_str(raw))
        except Exception:
            continue
        if 2.5 <= x <= 5.5:
            nums.append(x)

    # dedupe manteniendo orden
    uniq = []
    for x in nums:
        if x not in uniq:
            uniq.append(x)

    if len(uniq) >= 2:
        buy, sell = (uniq[0], uniq[1]) if uniq[0] <= uniq[1] else (uniq[1], uniq[0])
        return buy, sell

    return None, None

async def scrap_misterdollar():
    casa = "MisterDollar"
    url = "https://misterdollar.pe/"

    # endpoint Drupal Views AJAX (el que encontraste)
    endpoint = "https://misterdollar.pe/views/ajax"
    params = {
        "_wrapper_format": "drupal_ajax",
        "view_name": "view_block_tasaactual",
        "view_display_id": "block_1",
        "view_args": "",
        "view_path": "/front",
        "view_base_path": "",
        # view_dom_id cambia por sesión/página. PERO muchas veces NO es obligatorio.
        # Si fallara, lo sacamos primero del HTML principal. (Te dejo fallback abajo)
        "pager_element": "0",
        "_drupal_ajax": "1",
        "ajax_page_state[theme]": "tema",
        "ajax_page_state[theme_token]": "",
        # libraries puede cambiar; normalmente no es obligatorio para la respuesta del view.
        # Lo omitimos a propósito.
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=20, follow_redirects=True) as client:
            r = await client.get(endpoint, params=params)
            # Si el endpoint exige algún param, aquí podría dar 4xx, lo manejamos:
            if r.status_code >= 400:
                # fallback: intenta solo HTML principal (tu debug_analyze ya dijo que trae tasas)
                home = await client.get(url)
                home.raise_for_status()
                html = home.text or ""
                # extrae por repetición (simple)
                matches = [float(_to_float_str(m.group(0))) for m in RATE_RE.finditer(html)
                           if 2.5 <= float(_to_float_str(m.group(0))) <= 5.5]
                uniq = []
                for x in matches:
                    if x not in uniq:
                        uniq.append(x)
                buy = uniq[0] if len(uniq) > 0 else None
                sell = uniq[1] if len(uniq) > 1 else None
            else:
                payload = r.json()
                buy, sell = _extract_rates_from_insert_html(payload)

        compra = normalize_rate(str(buy)) if buy is not None else None
        venta  = normalize_rate(str(sell)) if sell is not None else None

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        out = {
            "casa": casa,
            "url": url,
            "compra": compra,
            "venta": venta,
            "estado": "cerrado" if cerrado else "abierto",
        }

        if compra is None or venta is None:
            out["estado"] = "error"
            out["error"] = "No se pudo identificar compra/venta (Drupal AJAX cambió o faltan params)."

        return out

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "compra": None,
            "venta": None,
            "estado": "error",
            "error": f"No se pudo scrapear: {e}",
        }
