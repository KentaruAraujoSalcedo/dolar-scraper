"""Validate SUNAT month data before reusing or publishing it."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from .health import finite_rate


def valid_sunat(data):
    if not isinstance(data, dict):
        return False
    days = data.get("dias")
    month = data.get("mes")
    if not isinstance(month, str) or len(month) != 7 or not isinstance(days, list) or not days:
        return False
    try:
        first = date.fromisoformat(month + "-01")
    except ValueError:
        return False
    if first.strftime("%Y-%m") != month:
        return False
    seen = set()
    for day in days:
        if not isinstance(day, dict):
            return False
        try:
            parsed = date.fromisoformat(day.get("fecha", ""))
        except (TypeError, ValueError):
            return False
        if parsed.strftime("%Y-%m") != month or parsed in seen:
            return False
        seen.add(parsed)
        if not finite_rate(day.get("compra")) or not finite_rate(day.get("venta")):
            return False
        if day["compra"] > day["venta"]:
            return False
    return True


def load_sunat(path):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return raw if valid_sunat(raw) else None
    except (OSError, ValueError, UnicodeError):
        return None


def already_updated_today(path, today_iso):
    data = load_sunat(path)
    return data is not None and data.get("run_date") == today_iso and data.get("mes") == today_iso[:7]


def atomic_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
