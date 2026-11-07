"""Full orchestrator test with 51 fake providers, no internet or credentials."""
import ast
import asyncio
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


class SimulatedPipelineTests(unittest.TestCase):
    def test_generate_diagnostics_and_preserve_sunat_on_failure(self):
        source = Path(__file__).resolve().parents[1] / "run_scrapers.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("scrapers.")]
        originals = {node.module: sys.modules.get(node.module) for node in imports}
        previous_runner = sys.modules.get("run_scrapers")
        try:
            for node in imports:
                module = types.ModuleType(node.module)
                provider = node.module.removeprefix("scrapers.")
                if provider == "sunat":
                    async def fetch_sunat():
                        now = datetime.now(ZoneInfo("America/Lima"))
                        return {
                            "casa": "SUNAT", "mes": now.strftime("%Y-%m"),
                            "dias": [{"fecha": now.date().isoformat(), "compra": 3.43, "venta": 3.45}],
                        }
                    setattr(module, node.names[0].name, fetch_sunat)
                else:
                    async def scrape(name=provider):
                        base = {"casa": name, "url": "https://example.org/", "compra": 3.43, "venta": 3.45}
                        if name == "cambiodigitalperu":
                            base.update(compra=None, venta=None, error="404 Authorization: private-token-123", error_type="error")
                        elif name == "cambiomundial":
                            base.update(compra=None, venta=None, source="blocked", error_type="blocked_cloudflare", error="cf challenge")
                        elif name == "moneyplus":
                            base.update(compra=3.30, venta=3.50)
                        elif name == "billex":
                            base.update(compra=3.33, venta=3.42)
                        return base
                    setattr(module, node.names[0].name, scrape)
                sys.modules[node.module] = module
            sys.modules.pop("run_scrapers", None)
            runner = importlib.import_module("run_scrapers")
            with tempfile.TemporaryDirectory() as dirname:
                old_dir = os.getcwd()
                try:
                    os.chdir(dirname)
                    with patch.dict(os.environ, {"GITHUB_RUN_ID": "TEST", "GITHUB_STEP_SUMMARY": str(Path(dirname)/"summary.md")}):
                        asyncio.run(runner.main())
                    tasas = json.loads(Path("data/tasas.json").read_text())
                    meta = json.loads(Path("data/meta.json").read_text())
                    diagnostic = json.loads(Path("data/diagnostico_scrapers.json").read_text())
                    self.assertEqual(len(tasas), 51)
                    self.assertEqual(meta["ok_total"], 48)
                    self.assertEqual(diagnostic["validas"], 48)
                    self.assertEqual(len(diagnostic["casas"]), 51)
                    self.assertEqual(meta["run_id"], "TEST")
                    self.assertNotIn("private-token", json.dumps(tasas))
                    self.assertNotIn("private-token", json.dumps(meta))
                    self.assertEqual(json.loads(Path("data/sunat_status.json").read_text())["estado"], "actualizado")
                    cached = json.loads(Path("data/sunat_mensual.json").read_text())
                    cached["run_date"] = (datetime.now(ZoneInfo("America/Lima"))-timedelta(days=1)).date().isoformat()
                    Path("data/sunat_mensual.json").write_text(json.dumps(cached))
                    async def failing_sunat():
                        raise RuntimeError("temporary failure, sensitive detail")

                    runner.scrap_sunat = failing_sunat

                    with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}):
                        asyncio.run(runner.main())
                    after = json.loads(Path("data/sunat_mensual.json").read_text())
                    status = json.loads(Path("data/sunat_status.json").read_text())
                    self.assertEqual(after, cached)
                    self.assertEqual(status["estado"], "conservado_por_error")
                finally:
                    os.chdir(old_dir)
        finally:
            for name, original in originals.items():
                if original is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = original
            if previous_runner is None:
                sys.modules.pop("run_scrapers", None)
            else:
                sys.modules["run_scrapers"] = previous_runner


if __name__ == "__main__":
    unittest.main()
