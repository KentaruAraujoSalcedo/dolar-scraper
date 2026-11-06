"""Upload guarded JSON to Cloudflare KV without external Python dependencies.

Usage in GitHub Actions:
    python -m infra.cloudflare_kv download-sunat
    python -m infra.cloudflare_kv publish

This module does NOT perform website scraping, and does not log credentials.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .health import validate_publication
from .sunat_guard import load_sunat, valid_sunat

KEYS = ("tasas.json", "meta.json", "diagnostico_scrapers.json")
RETRIES = 3


class KVError(RuntimeError):
    pass


def _config():
    env = {key: os.environ.get(key, "").strip() for key in ("CF_ACCOUNT_ID", "CF_KV_NAMESPACE_ID", "CF_API_TOKEN")}
    missing = [key for key, value in env.items() if not value]
    if missing:
        raise KVError("Cloudflare: faltan variables/secrets: " + ", ".join(missing))
    return env


def _endpoint(config, key):
    return (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{quote(config['CF_ACCOUNT_ID'], safe='')}/storage/kv/namespaces/"
        f"{quote(config['CF_KV_NAMESPACE_ID'], safe='')}/values/{quote(key, safe='')}"
    )


def _request(config, key, *, payload=None):
    url = _endpoint(config, key)
    headers = {"Authorization": "Bearer " + config["CF_API_TOKEN"], "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=headers, method="PUT" if payload is not None else "GET")
    for attempt in range(RETRIES):
        try:
            with urlopen(request, timeout=25) as response:
                result = response.read()
            return result
        except HTTPError as exc:
            if payload is None and exc.code == 404:
                return None
            # Retry only transient, not authentication or misconfiguration errors.
            if exc.code not in (429, 500, 502, 503, 504) or attempt + 1 >= RETRIES:
                raise KVError(f"Cloudflare KV: HTTP {exc.code} al {'subir' if payload is not None else 'descargar'} {key}") from None
        except (URLError, TimeoutError, OSError) as exc:
            if attempt + 1 >= RETRIES:
                raise KVError(f"Cloudflare KV: error de red al {'subir' if payload is not None else 'descargar'} {key}") from None
        time.sleep(2 ** attempt)
    raise KVError("Cloudflare KV: error inesperado")


def download_sunat():
    config = _config()
    raw = _request(config, "sunat_mensual.json")
    target = Path("data/sunat_mensual.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    if raw is None:
        target.unlink(missing_ok=True)
        print("SUNAT: no existe todavía un histórico en KV; se intentará extraer")
        return
    try:
        payload = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        payload = None
    if not valid_sunat(payload):
        target.unlink(missing_ok=True)
        print("SUNAT: el histórico descargado no es válido; se intentará extraer")
        return
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SUNAT: histórico válido recuperado: {len(payload['dias'])} días del mes {payload['mes']}")


def _upload(config, key, path):
    raw = Path(path).read_bytes()
    try:
        parsed = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        raise KVError(f"El archivo {path} no es JSON válido") from None
    result = _request(config, key, payload=json.dumps(parsed, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    try:
        response = json.loads(result)
    except (TypeError, UnicodeError, json.JSONDecodeError):
        raise KVError(f"Cloudflare no confirmó la subida de {key}") from None
    if response.get("success") is not True:
        raise KVError(f"Cloudflare rechazó la subida de {key} (success=false)")
    print(f"✅ KV: {key} publicado")


def publish():
    """Validate *all* payloads before writing any live key.

    Existing live keys are not deleted, and the SUNAT key is only changed if a
    fresh valid scrape exists. KV has no multi-key transaction: consumers may
    still briefly observe different versions while writes propagate.
    """
    base = Path("data")
    def read(key):
        try:
            return json.loads((base / key).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise KVError(f"Archivo obligatorio no encontrado o JSON inválido: {key}") from None

    tasas = read("tasas.json")
    meta = read("meta.json")
    diagnostics = read("diagnostico_scrapers.json")
    sunat_status = read("sunat_status.json")

    min_valid = int(os.environ.get("MIN_VALID_QUOTES", "30"))
    if not (1 <= min_valid <= 51):
        raise KVError("MIN_VALID_QUOTES debe estar entre 1 y 51")
    try:
        count = validate_publication(tasas, meta, min_valid=min_valid)
    except ValueError as exc:
        raise KVError(f"Publicación detenida: {exc}") from None
    if diagnostics.get("validas") != count or diagnostics.get("total") != len(tasas):
        raise KVError("Diagnóstico y cotizaciones no coinciden; no se publicará")
    if diagnostics.get("run_at_utc") != meta.get("run_at_utc"):
        raise KVError("Diagnóstico y metadatos pertenecen a diferentes ejecuciones")

    fresh_sunat = sunat_status.get("estado") == "actualizado" and sunat_status.get("actualizado") is True
    if fresh_sunat and load_sunat(base / "sunat_mensual.json") is None:
        raise KVError("SUNAT marcado como actualizado pero su JSON es inválido")

    # Pre-flight complete. Preserve prior KV keys if validation fails.
    config = _config()
    print(f"Protección aprobada: {count}/{len(tasas)} cotizaciones válidas (mínimo {min_valid})")
    for key in KEYS:
        _upload(config, key, base / key)
    if fresh_sunat:
        _upload(config, "sunat_mensual.json", base / "sunat_mensual.json")
    else:
        print(f"SUNAT: no se sobrescribe KV (estado: {sunat_status.get('estado')})")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("download-sunat", "publish"):
        print("Uso: python -m infra.cloudflare_kv download-sunat|publish", file=sys.stderr)
        return 2
    try:
        (download_sunat if sys.argv[1] == "download-sunat" else publish)()
        return 0
    except (KVError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
