# run_scrapers.py
import asyncio
import json
import os
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
from scrapers.sunat import scrap_sunat  # ✅ SOLO para sunat_mensual.json (no va a tasas)
from scrapers.tkambio import scrap_tkambio
from scrapers.tucambista import scrap_tucambista
from scrapers.vipcapitalbusiness import scrap_vipcapitalbusiness
from scrapers.westernunion import scrap_westernunion
from scrapers.x_cambio import scrap_x_cambio
from scrapers.yanki import scrap_yanki
from scrapers.zonadolar import scrap_zonadolar


def is_valid_rate(item: dict) -> bool:
    try:
        return item.get("compra") is not None and item.get("venta") is not None
    except Exception:
        return False


def fix_inverted_compra_venta(items):
    for r in items:
        if not isinstance(r, dict):
            continue
        c = r.get("compra")
        v = r.get("venta")
        if isinstance(c, (int, float)) and isinstance(v, (int, float)) and c > v:
            r["compra"], r["venta"] = v, c
            r["swapped"] = True
    return items


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
    Retorna dict SIEMPRE.
    """
    async with sem:
        try:
            res = await asyncio.wait_for(coro, timeout=timeout_s)

            if res is None or not isinstance(res, dict):
                return {
                    "casa": name,
                    "url": None,
                    "compra": None,
                    "venta": None,
                    "scraper_error": "returned_none_or_not_dict",
                }

            if not res.get("casa"):
                res["casa"] = name

            res.setdefault("url", None)
            return res

        except asyncio.TimeoutError:
            return {
                "casa": name,
                "url": None,
                "compra": None,
                "venta": None,
                "scraper_error": f"timeout_{timeout_s}s",
            }

        except Exception as e:
            return {
                "casa": name,
                "url": None,
                "compra": None,
                "venta": None,
                "scraper_error": str(e),
            }


async def main():
    run_at = datetime.now(timezone.utc).isoformat(timespec="minutes")
    hoy_lima = datetime.now(ZoneInfo("America/Lima")).date().isoformat()

    # ✅ Concurrencia (ajusta 10–25 según estabilidad)
    sem = asyncio.Semaphore(15)

    # ---- Lista de scrapers (SIN SUNAT en tasas) ----
    tasks = [
        ("acomo", scrap_acomo()),
        ("billex", scrap_billex()),
        ("cambiafx", scrap_cambiafx()),
        ("cambiodigitalperu", scrap_cambiodigitalperu()),
        ("cambiomas", scrap_cambiomas()),
        ("cambiomundial", scrap_cambiomundial(), 80),
        ("cambioseguro", scrap_cambioseguro()),
        ("cambioselgordito", scrap_cambioselgordito()),
        ("cambiosol", scrap_cambiosol()),
        ("cambiox", scrap_cambiox()),
        ("cambix", scrap_cambix()),
        ("chapacambio", scrap_chapacambio()),
        ("chaskidolar", scrap_chaskidolar()),
        ("defiperu", scrap_defiperu()),
        ("dichikash", scrap_dichikash()),
        ("dinekash", scrap_dinekash()),
        ("dinersfx", scrap_dinersfx()),
        ("dolarex", scrap_dolarex()),
        ("dollarhouse", scrap_dollarhouse()),
        ("global66", scrap_global66()),
        ("hirpower", scrap_hirpower()),
        ("inkamoney", scrap_inkamoney()),
        ("intercambialo", scrap_intercambialo()),
        ("inticambio", scrap_inticambio()),
        ("jetperu", scrap_jetperu()),
        ("kallpacambios", scrap_kallpacambios()),
        ("kambio", scrap_kambio()),
        ("kambista", scrap_kambista()),
        ("marketdollar", scrap_marketdollar()),
        ("megamoney", scrap_megamoney()),
        ("mercadocambiario", scrap_mercadocambiario()),
        ("midpointfx", scrap_midpointfx()),
        ("misterdollar", scrap_misterdollar()),
        ("moneyhouse", scrap_moneyhouse()),
        ("moneyplus", scrap_moneyplus()),
        ("okane", scrap_okane()),
        ("perudolar", scrap_perudolar()),
        ("rextie", scrap_rextie()),
        ("rissanpe", scrap_rissanpe()),
        ("roblex", scrap_roblex()),
        ("safex", scrap_safex()),
        ("securex", scrap_securex()),
        ("smartdollar", scrap_smartdollar()),
        ("srcambio", scrap_srcambio()),
        ("tkambio", scrap_tkambio()),
        ("tucambista", scrap_tucambista()),
        ("vipcapitalbusiness", scrap_vipcapitalbusiness()),
        ("westernunion", scrap_westernunion()),
        ("x_cambio", scrap_x_cambio()),
        ("yanki", scrap_yanki()),
        ("zonadolar", scrap_zonadolar()),
    ]

    # ✅ Ejecutar en paralelo
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

    # source/estado: conserva diagnóstico del scraper
    for r in resultados:
        valid = is_valid_rate(r)

        # si el scraper ya definió source (ej: httpx/playwright), respétalo
        if "source" not in r:
            r["source"] = "scraper" if valid else "missing"

        # si no es válido, marca error sin borrar info
        if not valid:
            r.setdefault("estado", "error")
            # prioriza error propio, luego scraper_error de _safe_call, sino genérico
            r.setdefault("error", r.get("scraper_error") or "missing compra/venta")

    resultados = fix_inverted_compra_venta(resultados)

    os.makedirs("data", exist_ok=True)

    with open("data/tasas.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print("✅ Tasas guardadas en data/tasas.json")

    ok = [r["casa"] for r in resultados if r.get("source") == "scraper"]
    ms = [r["casa"] for r in resultados if r.get("source") == "missing"]

    fails = [
    {"casa": r.get("casa"), "error": (r.get("scraper_error") or r.get("error"))}
    for r in resultados
    if (
        (r.get("scraper_error") or r.get("error") or r.get("estado") == "error")
        and r.get("estado") != "bloqueado"
    )
    ]
    
    meta = {
        "run_at_utc": run_at,
        "run_date": hoy_lima,
        "total": len(resultados),
        "ok_scraper": len(ok),
        "missing": len(ms),
        "ok_list": ok,
        "missing_list": ms,
        "scraper_errors": fails[:80],
    }

    with open("data/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("🧾 Meta guardada en data/meta.json")

    # ===============================
    # ✅ SUNAT MENSUAL (separado)
    # Solo 1 vez al día
    # ===============================

    out_path = "data/sunat_mensual.json"

    if already_updated_today(out_path, hoy_lima):
        print("✅ SUNAT mensual ya fue actualizado hoy. Skipping.")
    else:
        # SUNAT puede ser más lento: timeout mayor
        sunat_mensual = await _safe_call("sunat_mensual", scrap_sunat(), sem, timeout_s=90)

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
                "error": (sunat_mensual.get("scraper_error") if isinstance(sunat_mensual, dict) else "unknown"),
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"⚠️ SUNAT mensual FALLÓ. Se guardó {out_path} con error para no romper el workflow.")

if __name__ == "__main__":
    asyncio.run(main())
