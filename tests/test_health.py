import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from infra.health import (
    diagnostic_code, make_diagnostics, safe_meta_errors, safe_public_result,
    validate_publication, export_diagnostics_csv, write_action_summary,
)


class HealthTests(unittest.TestCase):
    def test_codes_classify_realworld_errors(self):
        cases = [
            ({"source": "missing", "error_type": "error", "error": "Client error 404 Not Found"}, "http_404"),
            ({"source": "missing", "error_type": "error", "error": "Name or service not known"}, "dns_error"),
            ({"source": "missing", "error_type": "blocked_403", "error": "403"}, "blocked_403"),
            ({"source": "blocked", "error_type": "blocked_cloudflare", "error": "challenge"}, "blocked_cloudflare"),
            ({"source": "outlier", "error_type": "outlier_spread_high", "error": "spread=0.2"}, "outlier_spread_high"),
            ({"source": "regular", "error": "spread"}, "spread_alto"),
        ]
        for item, code in cases:
            with self.subTest(code=code):
                self.assertEqual(diagnostic_code(item), code)

    def test_public_results_hide_traceback_and_outlier_numbers(self):
        item = {
            "casa": "Test", "source": "outlier", "compra": 3.3, "venta": 3.5,
            "error": "Bearer PRIVATE123; https://server.internal/private", "error_type": "outlier_spread_high",
            "traceback_last_lines": ["Authorization: PRIVATE123"], "extra_password": "PRIVATE123",
        }
        result = safe_public_result(item)
        blob = json.dumps(result)
        self.assertNotIn("PRIVATE123", blob)
        self.assertNotIn("extra_password", blob)
        self.assertNotIn("traceback", blob)
        self.assertIsNone(result["compra"])
        self.assertIsNone(result["venta"])
        meta = safe_meta_errors([item])
        self.assertNotIn("PRIVATE123", json.dumps(meta))
        self.assertEqual(meta[0]["error_type"], "outlier_spread_high")

    def test_diagnostics_json_csv_one_row_per_house_and_sorted(self):
        rows = [
            {"casa": "A", "source": "scraper", "compra": 3.42, "venta": 3.45, "elapsed_ms": 40},
            {"casa": "B", "source": "regular", "compra": 3.40, "venta": 3.47, "elapsed_ms": 70},
            {"casa": "C", "source": "missing", "compra": None, "venta": None, "error": "404", "elapsed_ms": 100},
            {"casa": "D", "source": "blocked", "error_type": "blocked_403", "elapsed_ms": 120},
            {"casa": "E", "source": "outlier", "error_type": "outlier_spread_high", "compra": 3.1, "venta": 3.4},
        ]
        diagnosis = make_diagnostics(rows, run_at_utc="2026-11-06T18:51+00:00", run_date="2026-11-06")
        self.assertEqual(diagnosis["total"], 5)
        self.assertEqual(diagnosis["validas"], 2)
        self.assertEqual(diagnosis["casas"][0]["casa"], "D")
        self.assertEqual(diagnosis["casas"][-1]["casa"], "A")
        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "diagnostico.csv"
            summary_path = Path(td) / "summary.md"
            export_diagnostics_csv(csv_path, diagnosis)
            write_action_summary(diagnosis, summary_path)
            with csv_path.open(encoding="utf-8-sig", newline="") as f:
                contents = list(csv.DictReader(f))
            self.assertEqual(len(contents), 5)
            self.assertIn("C", {row["casa"] for row in contents})
            self.assertIn("Casa", summary_path.read_text())

    def test_publication_guard_good_and_bad_batches(self):
        good = [{"casa": f"test{i}", "source": "scraper", "compra": 3.43, "venta": 3.45} for i in range(40)]
        invalid = [{"casa": f"broken{i}", "source": "missing", "compra": None, "venta": None} for i in range(11)]
        meta = {"total": 51, "ok_total": 40, "run_at_utc": "2026-11-06T18:51Z", "run_date": "2026-11-06"}
        self.assertEqual(validate_publication(good + invalid, meta, min_valid=30), 40)
        poor = good[:20] + invalid + [dict(invalid[0], casa=f"missing{i}") for i in range(20)]
        bad_meta = {**meta, "ok_total": 20}
        with self.assertRaisesRegex(ValueError, "Protección activa"):
            validate_publication(poor, bad_meta, min_valid=30)
        with self.assertRaisesRegex(ValueError, "no coincide"):
            validate_publication(good + invalid, {**meta, "total": 50}, min_valid=30)
        with self.assertRaisesRegex(ValueError, "inválidos"):
            validate_publication(good + [None] + invalid[:-1], meta, min_valid=30)

    def test_diagnostics_are_json_serializable(self):
        rows = [{"casa": "test", "source": "scraper", "compra": 3.2, "venta": 3.3}]
        parsed = json.loads(json.dumps(make_diagnostics(rows, run_at_utc="now", run_date="today")))
        self.assertEqual(parsed["validas"], 1)


if __name__ == "__main__":
    unittest.main()
