import json
import tempfile
import unittest
from pathlib import Path
from infra.sunat_guard import valid_sunat, load_sunat, already_updated_today, atomic_json


class SunatTests(unittest.TestCase):
    def setUp(self):
        self.month = {
            "casa": "SUNAT", "mes": "2026-11", "run_date": "2026-11-06",
            "dias": [
                {"fecha": "2026-11-05", "compra": 3.44, "venta": 3.45},
                {"fecha": "2026-11-06", "compra": 3.44, "venta": 3.45},
            ],
        }

    def test_accept_valid_month(self):
        self.assertTrue(valid_sunat(self.month))
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "sunat_mensual.json"
            atomic_json(file, self.month)
            self.assertEqual(len(load_sunat(file)["dias"]), 2)
            self.assertTrue(already_updated_today(file, "2026-11-06"))
            self.assertFalse(already_updated_today(file, "2026-12-01"))

    def test_reject_empty_duplicate_mismatch_and_invalid_values(self):
        for changed in (
            {**self.month, "dias": []},
            {**self.month, "dias": [self.month["dias"][0]] * 2},
            {**self.month, "mes": "2026-12"},
            {**self.month, "dias": [{"fecha": "2026-11-06", "compra": 3.5, "venta": 3.4}]},
            {**self.month, "dias": [{"fecha": "2026-11-06", "compra": float("nan"), "venta": 3.4}]},
        ):
            with self.subTest(changed=changed):
                self.assertFalse(valid_sunat(changed))

    def test_invalid_payload_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "sunat_mensual.json"
            file.write_text('{"success":false,"errors":[]}', encoding="utf-8")
            self.assertIsNone(load_sunat(file))
            self.assertFalse(already_updated_today(file, "2026-11-06"))


if __name__ == "__main__":
    unittest.main()
