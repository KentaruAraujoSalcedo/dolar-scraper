# run_scrapers.py
import asyncio
import json
import os
import time
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ===== IMPORTS DE SCRAPERS =====
from scrapers.acomo import scrap_acomo
from scrapers.billex import scrap_billex
from scrapers.cambiafx import scrap_cambiafx
from scrapers.cambiodigitalperu import scrap_cambiodigitalperu
from scrapers.cambiomas import scrap_cambiomas
from scrapers.cambiomundial import scrap_cambiomundial
from scrapers.cambioseguro import scrap_cambioseguro
from scrapers.cambioselgordito import scrap_cambioselgordito
from scrapers.cambiosol import scrap_cambiosol
from scrapers.cambiox import scrap_cambiox
from scrapers.cambix import scrap_cambix
from scrapers.chapacambio import scrap_chapacambio
from scrapers.chaskidolar import scrap_chaskidolar
from scrapers.defiperu import scrap_defiperu
from scrapers.dichikash import scrap_dichikash
from scrapers.dinekash import scrap_dinekash
from scrapers.dinersfx import scrap_dinersfx
from scrapers.dolarex import scrap_dolarex
from scrapers.dollarhouse import scrap_dollarhouse
from scrapers.global66 import scrap_global66
from scrapers.hirpower import scrap_hirpower
from scrapers.inkamoney import scrap_inkamoney
from scrapers.intercambialo import scrap_intercambialo
from scrapers.inticambio import scrap_inticambio
from scrapers.jetperu import scrap_jetperu
from scrapers.kallpacambios import scrap_kallpacambios
from scrapers.kambio import scrap_kambio
from scrapers.kambista import scrap_kambista
from scrapers.marketdollar import scrap_marketdollar
from scrapers.megamoney import scrap_megamoney
from scrapers.mercadocambiario import scrap_mercadocambiario
from scrapers.midpointfx import scrap_midpointfx
from scrapers.misterdollar import scrap_misterdollar
from scrapers.moneyhouse import scrap_moneyhouse
from scrapers.moneyplus import scrap_moneyplus
from scrapers.okane import scrap_okane
from scrapers.perudolar import scrap_perudolar
from scrapers.rextie import scrap_rextie
from scrapers.rissanpe import scrap_rissanpe
from scrapers.roblex import scrap_roblex
from scrapers.safex import scrap_safex
from scrapers.securex import scrap_securex
from scrapers.smartdollar import scrap_smartdollar
from scrapers.srcambio import scrap_srcambio
from scrapers.sunat import scrap_sunat  # ✅ SOLO sunat_mensual.json
from scrapers.tkambio import scrap_tkambio
from scrapers.tucambista import scrap_tucambista
from scrapers.vipcapitalbusiness import scrap_vipcapitalbusiness
from scrapers.westernunion import scrap_westernunion
from scrapers.x_cambio import scrap_x_cambio
from scrapers.yanki import scrap_yanki
from scrapers.zonadolar import scrap_zonadolar


# ----------------------------
# Config de sanidad / outliers
# ----------------------------
MIN_RATE = 3.00
MAX_RATE = 3.60
MAX_SPREAD = 0.05  # ajusta: 0.05 es estricto y te limpia outliers feos


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def is_valid_rate(item: dict) -> bool:
    try:
        return _is_number(item.get("compra")) and _is_number(item.get("venta"))
    except Exception:
        return False


def fix_inverted_compra_venta(item: dict) -> dict:
    c = item.get("compra")
    v = item.get("venta")
    if _is_number(c) and _is_number(v) and c > v:
        item["compra"], item["venta"] = v, c
        item["swapped"] = True
    return item


def validate_and_tag(item: dict) -> dict:
    """
    Aplica reglas de sanidad y etiqueta:
    - estado: ok / error / outlier / bloqueado
    - source: scraper / missing / outlier / blocked
    """
    c = item.get("compra")
    v = item.get("venta")

    if not is_valid_rate(item):
        item.setdefault("estado", "error")
        item.setdefault("source", "missing")
        item.setdefault("error", item.get("error") or "missing compra/venta")
        return item

    # Normaliza invertido si aplica
    item = fix_inverted_compra_venta(item)
    c = item.get("compra")
    v = item.get("venta")

    # Reglas de rango
    if not (MIN_RATE <= c <= MAX_RATE) or not (MIN_RATE <= v <= MAX_RATE):
        item["estado"] = "outlier"
        item["source"] = "outlier"
        item["error"] = f"outlier_range compra={c} venta={v} (expected {MIN_RATE}-{MAX_RATE})"
        # Si quieres ocultarlo del front, lo puedes nullear:
        item["compra"] = None
        item["venta"] = None
        return item

    # Spread máximo
    spread = v - c
    item["spread"] = round(spread, 6)
    if spread < 0:
        # ya debió corregirse con swapped, pero por si acaso
        item["estado"] = "error"
        item["source"] = "missing"
        item["error"] = f"negative_spread compra={c} venta={v}"
        item["compra"] = None
        item["venta"] = None
        return item

    if spread > MAX_SPREAD:
        item["estado"] = "outlier"
        item["source"] = "outlier"
        item["error"] = f"outlier_spread spread={spread:.6f} (max {MAX_SPREAD}) compra={c} venta={v}"
        item["compra"] = None
        item["venta"] = None
        return item

    item.setdefault("estado", "ok")
    item.setdefault("source", "scraper")
    return item


def classify_error(err: str) -> str:
    """
    Clasifica en categorías útiles para tu meta.
    """
    if not err:
        return "unknown"

    e = err.lower()

    if "timeout" in e:
        return "timeout"

    # Bloqueos típicos
    if "403" in e or "forbidden" in e:
        return "blocked_403"
    if "cloudflare" in e or "cf" in e:
        return "blocked_cloudflare"
    if "captcha" in e:
        return "blocked_captcha"
    if "blocked_or_session" in e or "error4" in e:
    return "blocked_or_session"

    # Parse/selector
    if "no se pudieron identificar" in e or "no se pudo identificar" in e or "parse" in e:
        return "parse_error"

    return "error"


def already_updated_today(path: str, hoy_iso: str) -> bool:
    """
    Devuelve True si sunat_mensual.json ya fue generado hoy y tiene dias válidos.
    """
    try:
        if not os.path.exists(path):
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            data.get("run_date") == hoy_iso
            and isinstance(data.get("dias"), list)
            and len(data["dias"]) > 0
        )
    except Exception:
        return False


async def _safe_call(name: str, coro, sem: asyncio.Semaphore, timeout_s: int = 25):
    """
    Ejecuta un scraper con límite de concurrencia + timeout.
    Retorna dict SIEMPRE, con diagnóstico.
    """
    async with sem:
        t0 = time.perf_counter()
        try:
            res = await asyncio.wait_for(coro, timeout=timeout_s)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            if res is None or not isinstance(res, dict):
                return {
                    "casa": name,
                    "url": None,
                    "compra": None,
                    "venta": None,
                    "estado": "error",
                    "source": "missing",
                    "elapsed_ms": elapsed_ms,
                    "error": "returned_none_or_not_dict",
                    "error_type": "returned_none_or_not_dict",
                }

            if not res.get("casa"):
                res["casa"] = name

            res.setdefault("url", None)
            res["elapsed_ms"] = elapsed_ms
            return res

        except asyncio.TimeoutError:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "casa": name,
                "url": None,
                "compra": None,
                "venta": None,
                "estado": "error",
                "source": "missing",
                "elapsed_ms": elapsed_ms,
                "error": f"timeout_{timeout_s}s",
                "error_type": "timeout",
            }

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            # intenta extraer status_code si viene en excepciones de httpx/requests
            status_code = None
            try:
                # httpx.HTTPStatusError tiene .response.status_code
                if hasattr(e, "response") and getattr(e, "response") is not None:
                    status_code = getattr(getattr(e, "response"), "status_code", None)
                # requests.exceptions.HTTPError a veces tiene .response.status_code
                if status_code is None and hasattr(e, "args"):
                    pass
            except Exception:
                status_code = None

            tb_lines = traceback.format_exc().splitlines()

            err_msg = str(e) or "exception_no_message"
            err_type = classify_error(err_msg)

            return {
                "casa": name,
                "url": None,
                "compra": None,
                "venta": None,
                "estado": "error",
                "source": "missing",
                "elapsed_ms": elapsed_ms,
                "error": err_msg,
                "error_type": err_type,
                "exception_type": type(e).__name__,
                "exception_message": err_msg,
                "status_code": status_code,
                "traceback_last_lines": tb_lines[-8:],
            }


async def main():
    run_at = datetime.now(timezone.utc).isoformat(timespec="minutes")
    hoy_lima = datetime.now(ZoneInfo("America/Lima")).date().isoformat()

    sem = asyncio.Semaphore(15)

    tasks = [
        ("Acomo", scrap_acomo()),
        ("Billex", scrap_billex()),
        ("CambiaFX", scrap_cambiafx()),
        ("CambioDigitalPeru", scrap_cambiodigitalperu()),
        ("CambiosMass", scrap_cambiomas()),
        ("CambioMundial", scrap_cambiomundial(), 80),
        ("CambioSeguro", scrap_cambioseguro()),
        ("Cambios El Gordito", scrap_cambioselgordito()),
        ("CambioSol", scrap_cambiosol()),
        ("CambioX", scrap_cambiox()),
        ("Cambix", scrap_cambix()),
        ("ChapaCambio", scrap_chapacambio()),
        ("ChaskiDolar", scrap_chaskidolar()),
        ("DefiPeru", scrap_defiperu()),
        ("Dichikash", scrap_dichikash()),
        ("DineKash", scrap_dinekash()),
        ("DinersFX", scrap_dinersfx()),
        ("Dolarex", scrap_dolarex()),
        ("DollarHouse", scrap_dollarhouse()),
        ("Global66", scrap_global66()),
        ("Hirpower", scrap_hirpower()),
        ("InkaMoney", scrap_inkamoney()),
        ("Intercambialo", scrap_intercambialo()),
        ("IntiCambio", scrap_inticambio()),
        ("JetPeru", scrap_jetperu()),
        ("KallpaCambios", scrap_kallpacambios()),
        ("Kambio", scrap_kambio()),
        ("Kambista", scrap_kambista()),
        ("MarketDollar", scrap_marketdollar()),
        ("MegaMoney", scrap_megamoney()),
        ("MercadoCambiario", scrap_mercadocambiario()),
        ("MidpointFX", scrap_midpointfx()),
        ("MisterDollar", scrap_misterdollar()),
        ("MoneyHouse", scrap_moneyhouse()),
        ("MoneyPlus", scrap_moneyplus()),
        ("OkaneCambioDigital", scrap_okane()),
        ("PeruDolar", scrap_perudolar()),
        ("Rextie", scrap_rextie()),
        ("Rissanpe", scrap_rissanpe()),
        ("Roblex", scrap_roblex()),
        ("Safex", scrap_safex()),
        ("Securex", scrap_securex()),
        ("SmartDollar", scrap_smartdollar()),
        ("SRcambio", scrap_srcambio()),
        ("TKambio", scrap_tkambio()),
        ("TuCambista", scrap_tucambista()),
        ("VipCapital", scrap_vipcapitalbusiness()),
        ("WesternUnion", scrap_westernunion()),
        ("X-Cambio", scrap_x_cambio()),
        ("Yanki", scrap_yanki()),
        ("ZonaDolar", scrap_zonadolar()),
    ]

    coros = []
    for item in tasks:
        if len(item) == 3:
            name, coro, timeout_s = item
        else:
            name, coro = item
            timeout_s = 25
        coros.append(_safe_call(name, coro, sem, timeout_s=timeout_s))

    resultados = await asyncio.gather(*coros)
    resultados = [r for r in resultados if isinstance(r, dict) and r.get("casa")]

    # Normaliza + valida + etiqueta
    final = []
    for r in resultados:
        r = validate_and_tag(r)

        # Si es OK, asegúrate que tenga estado=ok
        if r.get("source") == "scraper" and r.get("estado") not in ("outlier", "error", "bloqueado"):
            r["estado"] = "ok"

        # Si es cloudflare con null/null => bloqueado cloudflare
        if r.get("source") == "cloudflare" and (r.get("compra") is None or r.get("venta") is None):
            r["estado"] = "bloqueado"
            r["source"] = "blocked"
            r["error_type"] = "blocked_cloudflare"
            r.setdefault("error", "cloudflare_blocked_or_challenge")

        # Si es error/bloqueado y no tiene error_type, clasifica
        if r.get("estado") in ("error", "bloqueado"):
            err = r.get("error") or r.get("scraper_error") or ""
            r.setdefault("error_type", classify_error(err))

        # ✅ AQUÍ VA (normaliza 403/captcha/etc a source=blocked)
        if str(r.get("error_type", "")).startswith("blocked"):
            r["estado"] = "bloqueado"
            r["source"] = "blocked"

        final.append(r)

    os.makedirs("data", exist_ok=True)

    with open("data/tasas.json", "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print("✅ Tasas guardadas en data/tasas.json")

    ok_list = [r["casa"] for r in final if r.get("source") == "scraper" and r.get("estado") == "ok"]
    missing_list = [r["casa"] for r in final if r.get("source") == "missing"]
    outlier_list = [r["casa"] for r in final if r.get("source") == "outlier"]

    blocked_list = [
        r["casa"] for r in final
        if r.get("estado") == "bloqueado" or str(r.get("error_type", "")).startswith("blocked")
    ]

    # Errores detallados (no llenes infinito)
    fails = []
    for r in final:
        if r.get("estado") in ("error", "outlier", "bloqueado"):
            fails.append({
                "casa": r.get("casa"),
                "estado": r.get("estado"),
                "source": r.get("source"),
                "error_type": r.get("error_type"),
                "error": r.get("error"),
                "status_code": r.get("status_code"),
                "elapsed_ms": r.get("elapsed_ms"),
                "exception_type": r.get("exception_type"),
                "exception_message": r.get("exception_message"),
                "traceback_last_lines": r.get("traceback_last_lines"),
            })

    meta = {
        "run_at_utc": run_at,
        "run_date": hoy_lima,
        "total": len(final),
        "ok_scraper": len(ok_list),
        "missing": len(missing_list),
        "outliers": len(outlier_list),
        "blocked": len(blocked_list),
        "ok_list": ok_list,
        "missing_list": missing_list,
        "outlier_list": outlier_list,
        "blocked_list": blocked_list,
        "scraper_errors": fails[:120],
        "limits": {
            "min_rate": MIN_RATE,
            "max_rate": MAX_RATE,
            "max_spread": MAX_SPREAD,
            "concurrency": 15
        }
    }

    with open("data/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("🧾 Meta guardada en data/meta.json")

    # ===============================
    # ✅ SUNAT MENSUAL (separado)
    # ===============================
    out_path = "data/sunat_mensual.json"

    if already_updated_today(out_path, hoy_lima):
        print("✅ SUNAT mensual ya fue actualizado hoy. Skipping.")
    else:
        sunat_mensual = await _safe_call("SUNAT", scrap_sunat(), sem, timeout_s=90)

        if isinstance(sunat_mensual, dict) and isinstance(sunat_mensual.get("dias"), list) and sunat_mensual["dias"]:
            payload = {**sunat_mensual, "run_date": hoy_lima, "run_at_utc": run_at}
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"✅ SUNAT mensual guardado en {out_path} (dias={len(sunat_mensual['dias'])})")
        else:
            payload = {
                "casa": "SUNAT",
                "run_date": hoy_lima,
                "run_at_utc": run_at,
                "dias": [],
                "error": (sunat_mensual.get("error") if isinstance(sunat_mensual, dict) else "unknown"),
                "error_type": (sunat_mensual.get("error_type") if isinstance(sunat_mensual, dict) else "unknown"),
                "traceback_last_lines": (sunat_mensual.get("traceback_last_lines") if isinstance(sunat_mensual, dict) else None),
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print("⚠️ SUNAT mensual FALLÓ. Se guardó sunat_mensual.json con error para no romper el workflow.")


if __name__ == "__main__":
    asyncio.run(main())
