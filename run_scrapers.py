# run_scrapers.py
import asyncio
import json
import os
from pathlib import Path
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
from scrapers.dlsmoney import scrap_dlsmoney
from scrapers.dolarex import scrap_dolarex
from scrapers.dollarhouse import scrap_dollarhouse
from scrapers.global66 import scrap_global66
from scrapers.hirpower import scrap_hirpower
from scrapers.inkamoney import scrap_inkamoney
from scrapers.instakash import scrap_instakash
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
from scrapers.sunat import scrap_sunat  # <- se usa SOLO para sunat_mensual.json (no va a tasas)
from scrapers.tkambio import scrap_tkambio
from scrapers.tucambista import scrap_tucambista
from scrapers.vipcapitalbusiness import scrap_vipcapitalbusiness
from scrapers.westernunion import scrap_westernunion
from scrapers.x_cambio import scrap_x_cambio
from scrapers.yanki import scrap_yanki
from scrapers.zonadolar import scrap_zonadolar


# 1) Helper: correr scrapers sin que uno tumbe todo el proceso
async def _safe_call(name: str, coro):
    """
    Ejecuta un scraper y evita que una excepción tumbe todo el proceso.
    SIEMPRE retorna un dict (en caso de error o None, devuelve un dict con 'error').
    """
    try:
        res = await coro
        if res is None:
            print(f"⚠️ {name}: devolvió None")
            return {"casa": name, "url": None, "compra": None, "venta": None, "error": "returned_none"}
        return res
    except Exception as e:
        print(f"❌ {name}: error -> {e}")
        return {"casa": name, "url": None, "compra": None, "venta": None, "error": str(e)}


# 2) Backup: cargar backup_tasas.json (manual)
def load_backup_map(path="data/backup_tasas.json"):
    """
    Lee el backup manual y lo convierte en un mapa:
    backup_map["Rextie"] = {...datos...}
    Retorna (backup_map, fecha_backup).
    """
    p = Path(path)
    if not p.exists():
        return {}, None

    data = json.loads(p.read_text(encoding="utf-8"))
    fecha_backup = data.get("fecha_backup")
    casas = data.get("casas", [])

    backup_map = {
        c.get("casa"): c
        for c in casas
        if isinstance(c, dict) and c.get("casa")
    }
    return backup_map, fecha_backup


def is_valid_rate(item: dict) -> bool:
    """True si el scraper devolvió compra y venta (no None)."""
    try:
        return item.get("compra") is not None and item.get("venta") is not None
    except Exception:
        return False


def fix_inverted_compra_venta(items):
    """
    Corrige casas que vienen con compra/venta invertidas.
    En USD/PEN normalmente compra < venta.
    Si compra > venta, las intercambia.
    """
    for r in items:
        if not isinstance(r, dict):
            continue
        c = r.get("compra")
        v = r.get("venta")

        if isinstance(c, (int, float)) and isinstance(v, (int, float)):
            if c > v:
                r["compra"], r["venta"] = v, c
                r["swapped"] = True  # debug opcional
    return items


def apply_fallbacks(results, last_map, backup_map, fecha_backup=None):
    """
    Mezcla resultados con:
      - scraper válido
      - last known (auto)
      - backup manual
      - missing
    1 SOLO item por casa.
    """
    merged_by_casa = {}

    for r in results:
        if not isinstance(r, dict):
            continue

        casa = r.get("casa")
        if not casa:
            continue

        b = backup_map.get(casa)
        lk = last_map.get(casa) if isinstance(last_map, dict) else None

        # 1) Scraper válido
        if is_valid_rate(r):
            r["source"] = "scraper"
            merged_by_casa[casa] = r
            continue

        # 2) Last known válido
        if isinstance(lk, dict) and lk.get("compra") is not None and lk.get("venta") is not None:
            merged_item = {
                "casa": casa,
                "url": r.get("url") or lk.get("url") or (b.get("url") if isinstance(b, dict) else None),
                "compra": lk.get("compra"),
                "venta": lk.get("venta"),
                "source": "last_known",
                "last_seen": lk.get("last_seen"),
                "backup_fecha": fecha_backup,
            }
            if r.get("error"):
                merged_item["scraper_error"] = r["error"]
            merged_by_casa[casa] = merged_item
            continue

        # 3) Backup manual válido
        if isinstance(b, dict) and b.get("compra") is not None and b.get("venta") is not None:
            merged_item = {
                "casa": casa,
                "url": r.get("url") or b.get("url"),
                "compra": b.get("compra"),
                "venta": b.get("venta"),
                "source": "backup",
                "backup_fecha": fecha_backup,
            }
            if r.get("error"):
                merged_item["scraper_error"] = r["error"]
            merged_by_casa[casa] = merged_item
            continue

        # 4) Missing
        merged_item = {
            "casa": casa,
            "url": r.get("url")
                   or (lk.get("url") if isinstance(lk, dict) else None)
                   or (b.get("url") if isinstance(b, dict) else None),
            "source": "missing",
            "backup_fecha": fecha_backup,
        }
        if r.get("error"):
            merged_item["scraper_error"] = r["error"]
        merged_by_casa[casa] = merged_item

    return list(merged_by_casa.values())


# 2.5) Last known: cargar/guardar último valor válido (auto)
def load_last_known(path="data/last_known_tasas.json"):
    """
    Devuelve (last_map, updated_at)
    last_map["Rextie"] = {"casa":..., "url":..., "compra":..., "venta":..., "last_seen":"YYYY-MM-DD"}
    """
    p = Path(path)
    if not p.exists():
        return {}, None

    data = json.loads(p.read_text(encoding="utf-8"))
    updated_at = data.get("updated_at")
    casas = data.get("casas", {})
    if not isinstance(casas, dict):
        casas = {}
    return casas, updated_at


def save_last_known(last_map, updated_at, path="data/last_known_tasas.json"):
    payload = {"updated_at": updated_at, "casas": last_map}
    os.makedirs(Path(path).parent, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update_last_known_from_scraper_results(raw_results, last_map, hoy):
    """
    Recorre resultados crudos de scrapers y si una casa tiene compra/venta válidos,
    actualiza last_map[casa] con esos valores (y last_seen=hoy).
    """
    for r in raw_results:
        if not isinstance(r, dict):
            continue
        casa = r.get("casa")
        if not casa:
            continue
        if is_valid_rate(r):
            last_map[casa] = {
                "casa": casa,
                "url": r.get("url"),
                "compra": r.get("compra"),
                "venta": r.get("venta"),
                "last_seen": hoy,
            }
    return last_map


# 3) MAIN: ejecuta scrapers, aplica backup, guarda tasas, meta, y sunat_mensual (separado)
async def main():
    run_at = datetime.now(timezone.utc).isoformat(timespec="minutes")
    hoy_lima = datetime.now(ZoneInfo("America/Lima")).date().isoformat()

    # ---- Lista de scrapers (SIN SUNAT dentro de tasas) ----
    tasks = [
        ("acomo", scrap_acomo()),
        ("billex", scrap_billex()),
        ("cambiafx", scrap_cambiafx()),
        ("cambiodigitalperu", scrap_cambiodigitalperu()),
        ("cambiomas", scrap_cambiomas()),
        ("cambiomundial", scrap_cambiomundial()),
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
        # ("dlsmoney", scrap_dlsmoney()),
        ("dolarex", scrap_dolarex()),
        ("dollarhouse", scrap_dollarhouse()),
        ("global66", scrap_global66()),
        ("hirpower", scrap_hirpower()),
        ("inkamoney", scrap_inkamoney()),
        # ("instakash", scrap_instakash()),
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

    # ---- Ejecutar scrapers secuencialmente ----
    resultados = []
    for name, coro in tasks:
        resultados.append(await _safe_call(name, coro))

    # ---- Resultados crudos (incluye los dict con error) ----
    resultados_raw = [r for r in resultados if isinstance(r, dict) and r.get("casa")]

    # ---- Cargar last known ----
    last_map, last_updated_at = load_last_known("data/last_known_tasas.json")

    # ---- Actualizar last known con los scrapers OK hoy ----
    last_map = update_last_known_from_scraper_results(resultados_raw, last_map, hoy_lima)
    save_last_known(last_map, hoy_lima, "data/last_known_tasas.json")
    print("💾 Last-known actualizado (data/last_known_tasas.json)")

    # ---- Cargar backup manual ----
    backup_map, fecha_backup = load_backup_map("data/backup_tasas.json")

    # ---- Aplicar fallbacks ----
    resultados_final = apply_fallbacks(resultados_raw, last_map, backup_map, fecha_backup)
    print(f"🧩 Fallbacks aplicados (backup_fecha={fecha_backup}, last_known_updated_at={last_updated_at})")

    # ---- Fix inversión ----
    resultados_final = fix_inverted_compra_venta(resultados_final)

    # ---- Guardar tasas finales ----
    os.makedirs("data", exist_ok=True)
    with open("data/tasas.json", "w", encoding="utf-8") as f:
        json.dump(resultados_final, f, ensure_ascii=False, indent=2)
    print("✅ Tasas guardadas en data/tasas.json")

    # ---- Meta detallado ----
    ok = [r["casa"] for r in resultados_final if r.get("source") == "scraper" and r.get("casa")]
    lk = [r["casa"] for r in resultados_final if r.get("source") == "last_known" and r.get("casa")]
    bk = [r["casa"] for r in resultados_final if r.get("source") == "backup" and r.get("casa")]
    ms = [r["casa"] for r in resultados_final if r.get("source") == "missing" and r.get("casa")]

    fails = []
    for r in resultados_final:
        if r.get("scraper_error"):
            fails.append({"casa": r.get("casa"), "error": r.get("scraper_error")})

    meta = {
        "run_at_utc": run_at,
        "run_date": hoy_lima,
        "total": len(resultados_final),
        "ok_scraper": len(ok),
        "fallback_last_known": len(lk),
        "fallback_backup": len(bk),
        "missing": len(ms),
        "ok_list": ok,
        "fallback_last_known_list": lk,
        "fallback_backup_list": bk,
        "missing_list": ms,
        "scraper_errors": fails[:50],
    }

    with open("data/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("🧾 Meta guardada en data/meta.json")

    # ===============================
    # ✅ SUNAT MENSUAL (separado)
    # Siempre crea data/sunat_mensual.json (aunque falle), para que el workflow no se caiga
    # ===============================
    sunat_mensual = await _safe_call("sunat_mensual", scrap_sunat())

    os.makedirs("data", exist_ok=True)
    out_path = "data/sunat_mensual.json"

    # Si el scraper devolvió el formato esperado
    if isinstance(sunat_mensual, dict) and isinstance(sunat_mensual.get("dias"), list) and sunat_mensual["dias"]:
        payload = {
            **sunat_mensual,
            "run_date": hoy_lima,
            "run_at_utc": run_at,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"✅ SUNAT mensual guardado en {out_path} (dias={len(sunat_mensual['dias'])})")
    else:
        # Guardamos un json “de error” pero válido
        payload = {
            "casa": "SUNAT",
            "run_date": hoy_lima,
            "run_at_utc": run_at,
            "dias": [],
            "error": (sunat_mensual.get("error") if isinstance(sunat_mensual, dict) else "unknown"),
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"⚠️ SUNAT mensual FALLÓ. Se guardó {out_path} con error para no romper el workflow.")

if __name__ == "__main__":
    asyncio.run(main())
