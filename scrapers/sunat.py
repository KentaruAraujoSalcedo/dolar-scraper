import os
import re
import httpx
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Playwright fallback
from playwright.async_api import async_playwright

SUNAT_PAGE_URL = "https://www.sunat.gob.pe/cl-at-ittipcam/tcS01Alias"
SUNAT_API_URL  = "https://e-consulta.sunat.gob.pe/cl-at-ittipcam/tcS01Alias/listarTipoCambio"

LIMA_TZ = ZoneInfo("America/Lima")


def _ddmmyyyy_to_yyyymmdd(s: str):
    try:
        dd, mm, yyyy = s.strip().split("/")
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
    except Exception:
        return None


def _build_dias(rows):
    by_date = {}
    for it in rows:
        if not isinstance(it, dict):
            continue
        fec = it.get("fecPublica")
        val = it.get("valTipo")
        cod = it.get("codTipo")  # "C" compra, "V" venta

        fecha = _ddmmyyyy_to_yyyymmdd(fec) if fec else None
        if not fecha or val is None or cod not in ("C", "V"):
            continue

        try:
            rate = float(str(val).replace(",", ".").strip())
        except Exception:
            continue

        d = by_date.setdefault(fecha, {"fecha": fecha, "compra": None, "venta": None})
        if cod == "C":
            d["compra"] = rate
        else:
            d["venta"] = rate

    dias = [d for d in by_date.values()
            if isinstance(d.get("compra"), float) and isinstance(d.get("venta"), float)]
    dias.sort(key=lambda x: x["fecha"])
    return dias


# ----- Playwright fallback (tu versión, un poco compactada) -----
def _parse_fecha_from_data_date(data_date: str) -> str | None:
    if not data_date:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", str(data_date).strip())
    return m.group(1) if m else None


def _parse_compra_venta(texto: str):
    if not texto:
        return None, None
    t = " ".join(str(texto).split())

    compra = re.search(r"Compra\s+\"?\s*([\d.]+)", t, re.IGNORECASE)
    venta  = re.search(r"Venta\s+\"?\s*([\d.]+)", t, re.IGNORECASE)
    if compra and venta:
        try:
            return float(compra.group(1)), float(venta.group(1))
        except Exception:
            return None, None

    nums = re.findall(r"(\d+\.\d+)", t)
    if len(nums) >= 2:
        try:
            return float(nums[0]), float(nums[1])
        except Exception:
            return None, None
    return None, None


async def _scrap_sunat_playwright(year: int, month: int):
    url = SUNAT_PAGE_URL
    base = {"casa": "SUNAT", "url": url}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_selector("td[data-date]", timeout=60000)

        celdas = page.locator("td[data-date]")
        n = await celdas.count()
        if n == 0:
            await browser.close()
            return {**base, "error": "No se encontraron celdas td[data-date]", "dias": []}

        dias = []
        for i in range(n):
            celda = celdas.nth(i)
            data_date = await celda.get_attribute("data-date")
            fecha = _parse_fecha_from_data_date(data_date)
            if not fecha:
                continue

            # filtra solo el mes que queremos (opcional)
            if not fecha.startswith(f"{year}-{str(month).zfill(2)}"):
                continue

            texto = (await celda.inner_text()).strip()
            compra, venta = _parse_compra_venta(texto)
            if isinstance(compra, float) and isinstance(venta, float):
                dias.append({"fecha": fecha, "compra": compra, "venta": venta})

        dias.sort(key=lambda x: x["fecha"])
        await browser.close()

        if not dias:
            return {**base, "error": "Playwright: sin días parseables del mes", "dias": []}

        mes = dias[-1]["fecha"][:7]
        return {
            **base,
            "mes": mes,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dias": dias,
            "total_dias": len(dias),
            "source": "playwright_calendar",
        }


# ----- MAIN: API first, fallback Playwright -----
async def scrap_sunat():
    base = {"casa": "SUNAT", "url": SUNAT_PAGE_URL}

    now_lima = datetime.now(LIMA_TZ)
    year = int(os.getenv("SUNAT_YEAR", str(now_lima.year)))
    month = int(os.getenv("SUNAT_MONTH", str(now_lima.month)))
    mm = str(month).zfill(2)
    yyyy = str(year)

    headers_page = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": SUNAT_PAGE_URL,
    }

    headers_api = {
        "User-Agent": headers_page["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Origin": "https://e-consulta.sunat.gob.pe",
        "Referer": SUNAT_PAGE_URL,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    timeout = httpx.Timeout(30.0, connect=10.0)

    # 1) Try API via httpx
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # seed cookies
            await client.get(SUNAT_PAGE_URL, headers=headers_page)

            # call API (POST with month/year)
            r = await client.post(SUNAT_API_URL, headers=headers_api, data={"anio": yyyy, "mes": mm})
            r.raise_for_status()

            ct = (r.headers.get("content-type") or "").lower()
            if "json" not in ct and not (r.text or "").strip().startswith("["):
                # SUNAT sometimes returns HTML error page
                raise RuntimeError(f"API no JSON (ct={ct}) snippet={(r.text or '')[:180]}")

            rows = r.json()
            dias = _build_dias(rows)

            if not dias:
                raise RuntimeError("API OK pero sin días parseables")

            mes = dias[-1]["fecha"][:7]
            return {
                **base,
                "mes": mes,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "dias": dias,
                "total_dias": len(dias),
                "source": "sunat_api_httpx",
            }

    except Exception as e_api:
        # 2) Fallback to Playwright (reliable)
        out = await _scrap_sunat_playwright(year, month)
        # guarda razón del fallback (sin romper)
        out.setdefault("warning", f"Fallback a Playwright: {e_api}")
        return out
