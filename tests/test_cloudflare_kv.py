import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from infra import cloudflare_kv


class CloudflareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.enter = self.tmp.__enter__()
        self.cwd = os.getcwd()
        os.chdir(self.enter)
        Path("data").mkdir()
        self.good = [{"casa": f"casa{i}", "source": "scraper", "compra": 3.42, "venta": 3.46} for i in range(40)]
        self.meta = {"total": 40, "ok_total": 40, "run_at_utc": "2026-11-06T18:51+00:00", "run_date": "2026-11-06"}
        self.diag = {"total": 40, "validas": 40, "run_at_utc": self.meta["run_at_utc"]}
        self.sunat_status = {"estado": "sin_datos_por_error", "actualizado": False}
        for name, data in (("tasas.json", self.good), ("meta.json", self.meta), ("diagnostico_scrapers.json", self.diag), ("sunat_status.json", self.sunat_status)):
            (Path("data") / name).write_text(json.dumps(data), encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.__exit__(None, None, None)

    def test_guard_prevents_any_write_when_rates_crash(self):
        self.meta["ok_total"] = 15
        self.good = self.good[:15]
        self.meta["total"] = 15
        (Path("data") / "meta.json").write_text(json.dumps(self.meta), encoding="utf-8")
        (Path("data") / "tasas.json").write_text(json.dumps(self.good), encoding="utf-8")
        with patch.object(cloudflare_kv, "_config") as config, patch.object(cloudflare_kv, "_upload") as upload:
            with self.assertRaises(cloudflare_kv.KVError):
                cloudflare_kv.publish()
            config.assert_not_called()
            upload.assert_not_called()

    def test_publish_never_overwrites_sunat_without_fresh_data(self):
        with patch.object(cloudflare_kv, "_config", return_value={}) as config, patch.object(cloudflare_kv, "_upload") as upload:
            cloudflare_kv.publish()
            self.assertEqual([call.args[1] for call in upload.call_args_list], list(cloudflare_kv.KEYS))

    def test_invalid_sunat_marked_fresh_stops_all_writes(self):
        self.sunat_status = {"estado": "actualizado", "actualizado": True}
        (Path("data") / "sunat_status.json").write_text(json.dumps(self.sunat_status), encoding="utf-8")
        with patch.object(cloudflare_kv, "_config") as config, patch.object(cloudflare_kv, "_upload") as upload:
            with self.assertRaises(cloudflare_kv.KVError):
                cloudflare_kv.publish()
            config.assert_not_called()
            upload.assert_not_called()

    def test_download_rejects_cloudflare_error_json(self):
        with patch.object(cloudflare_kv, "_config", return_value={}), patch.object(cloudflare_kv, "_request", return_value=b'{"success":false,"errors":["bad"]}'):
            cloudflare_kv.download_sunat()
            self.assertFalse(Path("data/sunat_mensual.json").exists())


if __name__ == "__main__":
    unittest.main()
