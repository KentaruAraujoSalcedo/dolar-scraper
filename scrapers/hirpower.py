import httpx

async def scrap_hirpower():
    casa = "hirpower"
    url = "https://www.hirpower.com/"
    endpoint = "https://www.hirpower.com/config/getconfig"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
        "Origin": "https://www.hirpower.com",
        "X-Requested-With": "XMLHttpRequest",
    }

    timeout = httpx.Timeout(20.0, connect=10.0)

    def parse_num(x):
        if x is None:
            return None
        s = str(x).strip().replace("S/", "").replace(" ", "").replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None

    try:
        async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
            # 1) GET home para obtener cookies (ci_session + csrf_cookie_name)
            g = await client.get(url)
            g.raise_for_status()

            # 2) POST multipart como el navegador (csrf_test_name=undefined)
            files = {"csrf_test_name": (None, "undefined")}
            r = await client.post(endpoint, files=files)
            r.raise_for_status()

            ct = (r.headers.get("content-type") or "").lower()
            text = r.text or ""

            if "json" not in ct and not text.strip().startswith("{"):
                snippet = text[:350].replace("\n", " ").replace("\r", " ")
                return {
                    "casa": casa,
                    "url": url,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "error": f"Respuesta no JSON ({r.status_code}, ct={ct}). Snippet: {snippet}",
                }

            data = r.json()

        cfg = (data or {}).get("config") or {}

        base_raw = cfg.get("config_tipocambio_base")
        spread_c_raw = cfg.get("config_tipocambio_compra")
        spread_v_raw = cfg.get("config_tipocambio_venta")

        base = parse_num(base_raw)
        spread_c = parse_num(spread_c_raw)
        spread_v = parse_num(spread_v_raw)

        compra = None
        venta = None

        # Si vienen como spreads (ej: base=3.360 y compra/venta=0.010)
        if base is not None and spread_c is not None and spread_v is not None:
            # Si por algún cambio el "spread" viniera como tasa absoluta (>1), lo usamos directo
            if spread_c > 1 and spread_v > 1:
                compra = round(spread_c, 4)
                venta = round(spread_v, 4)
            else:
                compra = round(base - spread_c, 4)
                venta = round(base + spread_v, 4)

        cerrado = (compra is None and venta is None) or (compra == 0.0 and venta == 0.0)

        if compra is None or venta is None:
            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta,
                "estado": "error",
                "error": (
                    "No se pudieron calcular compra/venta. "
                    f"base={base_raw} spread_c={spread_c_raw} spread_v={spread_v_raw}"
                ),
            }

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
