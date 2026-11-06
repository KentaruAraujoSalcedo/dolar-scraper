"""Pure helpers for public scraper diagnostics and publication validation.

No external requests are performed here. Public diagnostics intentionally exclude
URLs, raw exception strings and tracebacks to avoid publishing secrets or internals.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

VALID_SOURCES = frozenset(("scraper", "regular"))
PROBLEM_SOURCES = frozenset(("missing", "outlier", "blocked"))
SOURCES = VALID_SOURCES | PROBLEM_SOURCES

DESCRIPTIONS = {
    "ok": "Cotización válida",
    "spread_alto": "Cotización válida; diferencia compra/venta elevada",
    "http_404": "Endpoint no encontrado (HTTP 404)",
    "blocked_403": "Acceso rechazado por el proveedor (HTTP 403)",
    "blocked_cloudflare": "El proveedor solicita una comprobación de acceso",
    "blocked_captcha": "El proveedor solicita CAPTCHA",
    "blocked_or_session": "Bloqueo de acceso o sesión inválida",
    "dns_error": "No se pudo resolver el dominio",
    "timeout": "Tiempo de espera agotado",
    "parse_error": "No se pudieron identificar las tasas",
    "missing_rates": "No se recibieron ambas tasas",
    "outlier_range": "Tasas fuera del rango de validación",
    "outlier_spread_high": "Diferencia compra/venta fuera de límites",
    "negative_spread": "Diferencia compra/venta inválida",
    "returned_none_or_not_dict": "Respuesta vacía o inválida",
    "error": "Error de extracción; revisar log de GitHub Actions",
    "unknown": "Sin diagnóstico detallado; revisar GitHub Actions",
}


def finite_rate(value):
    """Return True only for finite positive numeric rates (not booleans)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def diagnostic_code(item):
    """Standardized non-sensitive problem code, never a raw exception."""
    source = item.get("source")
    if source == "scraper":
        return "ok"
    if source == "regular":
        return "spread_alto"
    kind = str(item.get("error_type") or "").lower().strip()
    if kind in DESCRIPTIONS and kind not in ("error", "unknown"):
        return kind
    # Some scrapers return a generic 'error' even for a clear HTTP / DNS error.
    message = str(item.get("error") or "").lower()
    if "404" in message or "not found" in message:
        return "http_404"
    if "403" in message or "forbidden" in message:
        return "blocked_403"
    if "name or service not known" in message or "getaddrinfo" in message or "dns" in message:
        return "dns_error"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    if "missing compra/venta" in message or "missing rates" in message:
        return "missing_rates"
    if "parse" in message or "no se pudo identificar" in message:
        return "parse_error"
    return "error" if message else "unknown"


def safe_public_result(item):
    """Remove internal diagnostic strings while keeping the frontend JSON schema.

    The returned entry remains compatible with a tasas.json list. Failed / outlier
    entries never expose a numeric quote, even if a scraper returned one.
    """
    # Explicit allow-list: a future scraper cannot accidentally publish API
    # response bodies, authorization headers or additional debugging fields.
    allowed = (
        "casa", "url", "compra", "venta", "source", "spread", "swapped",
        "elapsed_ms", "fecha", "last_seen", "backup_fecha", "status_code",
        "error", "error_type",
    )
    result = {key: item[key] for key in allowed if key in item}
    source = result.get("source")
    code = diagnostic_code(item)
    for private_key in (
        "traceback_last_lines", "exception_type", "exception_message",
        "scraper_error", "debug", "headers", "response_body",
    ):
        result.pop(private_key, None)
    if source not in VALID_SOURCES:
        result["compra"] = None
        result["venta"] = None
        result["error_type"] = code
        result["error"] = DESCRIPTIONS.get(code, DESCRIPTIONS["unknown"])
    elif source == "regular":
        result["error_type"] = "spread_alto"
        result["error"] = DESCRIPTIONS["spread_alto"]
    else:
        result.pop("error", None)
        result.pop("error_type", None)
    return result


def make_diagnostics(entries, *, run_at_utc, run_date, run_id=None, sunat=None):
    """Create a per-house JSON suitable for Cloudflare KV and Actions artifacts."""
    rows = []
    for item in entries:
        status = item.get("source", "missing")
        code = diagnostic_code(item)
        valid = status in VALID_SOURCES and finite_rate(item.get("compra")) and finite_rate(item.get("venta"))
        duration = item.get("elapsed_ms")
        rows.append({
            "casa": str(item.get("casa") or "desconocida"),
            "estado": status,
            "valida": valid,
            "codigo": code,
            "motivo": DESCRIPTIONS.get(code, DESCRIPTIONS["unknown"]),
            "compra": item.get("compra") if valid else None,
            "venta": item.get("venta") if valid else None,
            "duracion_ms": duration if isinstance(duration, int) and duration >= 0 else None,
        })
    # Put failures on top to make inspection easy.
    priority = {"blocked": 0, "missing": 1, "outlier": 2, "regular": 3, "scraper": 4}
    rows.sort(key=lambda row: (priority.get(row["estado"], 1), row["casa"].casefold()))
    counts = Counter(row["estado"] for row in rows)
    result = {
        "schema_version": 1,
        "run_at_utc": run_at_utc,
        "run_date": run_date,
        "run_id": str(run_id) if run_id else None,
        "total": len(rows),
        "validas": sum(row["valida"] for row in rows),
        "por_estado": {source: counts.get(source, 0) for source in ("scraper", "regular", "missing", "blocked", "outlier")},
        "casas": rows,
        "nota": "Las tasas inválidas se muestran como null. No incluye excepciones ni credenciales.",
    }
    if isinstance(sunat, dict):
        result["sunat"] = {k: sunat.get(k) for k in ("estado", "dias", "mes", "actualizado")}
    return result


def export_diagnostics_csv(path, payload):
    columns = ("casa", "estado", "valida", "codigo", "motivo", "compra", "venta", "duracion_ms")
    with Path(path).open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in payload["casas"]:
            writer.writerow({key: row.get(key) for key in columns})


def safe_meta_errors(entries):
    """Keep meta.scraper_errors' familiar fields without publishing raw exceptions."""
    failures = []
    for item in entries:
        if item.get("source") not in PROBLEM_SOURCES:
            continue
        code = diagnostic_code(item)
        failures.append({
            "casa": item.get("casa"),
            "source": item.get("source"),
            "error_type": code,
            "error": DESCRIPTIONS.get(code, DESCRIPTIONS["unknown"]),
            "status_code": item.get("status_code") if isinstance(item.get("status_code"), int) else None,
            "elapsed_ms": item.get("elapsed_ms"),
            "exception_type": None,
            "exception_message": None,
            "traceback_last_lines": None,
        })
    return failures[:120]


def validate_publication(tasas, meta, *, min_valid=20):
    """Reject a severely degraded batch before updating any live KV keys."""
    if not isinstance(tasas, list) or len(tasas) < min_valid:
        raise ValueError(f"Cantidad de registros insuficiente: {len(tasas) if isinstance(tasas, list) else 'inválido'}")
    if not isinstance(meta, dict):
        raise ValueError("meta.json no es un objeto")
    if len(tasas) != meta.get("total"):
        raise ValueError("La cantidad de tasas no coincide con meta.total")
    if not all(isinstance(x, dict) and x.get("source") in SOURCES for x in tasas):
        raise ValueError("tasas.json contiene registros o estados inválidos")
    good = [x for x in tasas if x.get("source") in VALID_SOURCES and finite_rate(x.get("compra")) and finite_rate(x.get("venta")) and x["compra"] <= x["venta"]]
    if len(good) < min_valid:
        raise ValueError(f"Protección activa: solo {len(good)} cotizaciones válidas; mínimo {min_valid}")
    if len(good) != meta.get("ok_total"):
        raise ValueError("El conteo de tasas válidas no coincide con meta.ok_total")
    if not meta.get("run_at_utc") or not meta.get("run_date"):
        raise ValueError("Metadatos sin fecha de ejecución")
    return len(good)


def write_action_summary(diagnostics, destination):
    counts = diagnostics["por_estado"]
    failed = [r for r in diagnostics["casas"] if not r["valida"]]
    lines = [
        "## Estado de los scrapers",
        f"Ejecución: `{diagnostics['run_at_utc']}` | Válidas: **{diagnostics['validas']}/{diagnostics['total']}**",
        "",
        f"- Correctas: {counts['scraper']} | Regulares: {counts['regular']} | Sin datos: {counts['missing']} | Bloqueadas: {counts['blocked']} | Atípicas: {counts['outlier']}",
        "",
        "| Casa | Estado | Motivo |",
        "|---|---|---|",
    ]
    for r in failed:
        lines.append(f"| {r['casa']} | {r['estado']} | {r['motivo']} |")
    lines.extend(["", "Archivos descargables en *Artifacts*: `diagnostico_scrapers.json` y `diagnostico_scrapers.csv`."])
    with Path(destination).open("a", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
