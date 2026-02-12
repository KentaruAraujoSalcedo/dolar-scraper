import os
import json
import cloudscraper
from datetime import datetime, timezone, timedelta

SUNAT_PAGE_URL = "https://www.sunat.gob.pe/cl-at-ittipcam/tcS01Alias"
SUNAT_API_URL  = "https://e-consulta.sunat.gob.pe/cl-at-ittipcam/tcS01Alias/listarTipoCambio"

LIMA_TZ = timezone(timedelta(hours=-5))

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
        cod = it.get("codTipo")
        fecha = _ddmmyyyy_to_yyyymmdd(fec) if fec else None
        if not fecha or not val or cod not in ("C", "V"):
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
    dias = [d for d in by_date.values() if isinstance(d.get("compra"), float) and isinstance(d.get("venta"), float)]
    dias.sort(key=lambda x: x["fecha"])
    return dias

async def scrap_sunat():
    base = {"casa": "SUNAT", "url": SUNAT_PAGE_URL}
    now_lima = datetime.now(LIMA_TZ)
    year = int(os.getenv("SUNAT_YEAR", str(now_lima.year)))
    month = int(os.getenv("SUNAT_MONTH", str(now_lima.month)))
    mm = str(month).zfill(2)
    yyyy = str(year)

    try:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )

        # 1) Sembrar cookies
        scraper.get(SUNAT_PAGE_URL, timeout=25)

        # 2) Llamar API (primero sin params, luego con)
        r = scraper.get(SUNAT_API_URL, timeout=25)
        if r.status_code != 200 or not r.text.strip().startswith("["):
            r = scraper.post(SUNAT_API_URL, data={"anio": yyyy, "mes": mm}, timeout=25)

        r.raise_for_status()
        rows = r.json()

        dias = _build_dias(rows)
        if not dias:
            return {**base, "error": "Respuesta OK pero sin días parseables", "dias": []}

        mes = dias[-1]["fecha"][:7]
        return {
            **base,
            "mes": mes,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dias": dias,
            "total_dias": len(dias),
        }

    except Exception as e:
        return {**base, "error": str(e), "dias": []}
