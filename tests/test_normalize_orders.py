"""Regression and failure-behavior tests for the synthetic repair demo."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import normalize_orders as workflow


ROOT = Path(__file__).resolve().parents[1]
HEADER = "order_id,customer_ref,order_date,amount,currency\n"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "build"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="test-", dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "input.csv"
        self.output = self.directory / "output.json"

    def write_csv(self, text, encoding="utf-8"):
        self.source.write_text(text, encoding=encoding)
        return self.source

    def test_synthetic_export_preserves_ids_and_quoted_customer(self):
        result = workflow.normalize(ROOT / "examples" / "orders.csv", self.output)
        self.assertEqual(result["order_count"], 3)
        self.assertEqual(result["orders"][0], {
            "order_id": "00017", "customer_ref": "Demo, North",
            "order_date": "2026-09-01", "amount_minor": 1010, "currency": "USD",
        })
        self.assertEqual(result["totals_minor_by_currency"], {"EUR": 8900, "USD": 3000})
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8")), result)

    def test_money_uses_exact_minor_units(self):
        self.write_csv(HEADER + "01,Demo,2026-09-01,0.10,USD\n02,Demo,2026-09-01,0.20,USD\n")
        result = workflow.read_orders(self.source)
        self.assertEqual(result["totals_minor_by_currency"]["USD"], 30)
        self.assertIs(type(result["orders"][0]["amount_minor"]), int)

    def test_bom_reordered_headers_and_blank_lines(self):
        self.write_csv(
            "currency,amount,order_date,customer_ref,order_id\n\n"
            "gbp,12.5,02/29/2024,Demo,0001\n", encoding="utf-8-sig",
        )
        result = workflow.read_orders(self.source)
        self.assertEqual(result["orders"][0]["order_date"], "2024-02-29")
        self.assertEqual(result["orders"][0]["amount_minor"], 1250)

    def test_invalid_final_record_preserves_previous_output(self):
        self.output.write_text("previous accepted export\n", encoding="utf-8")
        with self.assertRaisesRegex(workflow.InputError, "line 3: amount"):
            workflow.normalize(ROOT / "examples" / "invalid_orders.csv", self.output)
        self.assertEqual(self.output.read_text(encoding="utf-8"), "previous accepted export\n")

    def test_duplicate_ids_rejected_after_whitespace_normalization(self):
        self.write_csv(HEADER + "001,Demo,2026-09-01,1,USD\n 001 ,Demo,2026-09-02,2,USD\n")
        with self.assertRaisesRegex(workflow.InputError, "line 3: duplicate.*first seen on line 2"):
            workflow.read_orders(self.source)

    def test_invalid_dates_are_rejected_without_guessing(self):
        for value in ("2026-02-29", "31/01/2026", "2026-13-01", "9/1/2026", "20260901"):
            with self.subTest(value=value), self.assertRaises(workflow.InputError):
                workflow.parse_date(value)

    def test_unsupported_amount_formats_are_rejected(self):
        for value in ("NaN", "Infinity", "1e3", "-10", "0", "19.999", "$10", "1,000", "01.25", "1000000000"):
            with self.subTest(value=value), self.assertRaises(workflow.InputError):
                workflow.parse_amount(value)

    def test_unknown_currency_and_empty_customer_are_rejected(self):
        for record in ("1,Demo,2026-09-01,1,JPY", "1,  ,2026-09-01,1,USD"):
            with self.subTest(record=record):
                self.write_csv(HEADER + record + "\n")
                with self.assertRaises(workflow.InputError):
                    workflow.read_orders(self.source)

    def test_missing_extra_and_duplicate_columns_are_rejected(self):
        for header in (
            "order_id,customer_ref,order_date,amount\n",
            "order_id,customer_ref,order_date,amount,currency,notes\n",
            "order_id,customer_ref,order_date,amount,amount\n",
        ):
            with self.subTest(header=header):
                self.write_csv(header + "1,Demo,2026-09-01,1,USD\n")
                with self.assertRaises(workflow.InputError):
                    workflow.read_orders(self.source)

    def test_incomplete_or_surplus_row_fields_are_rejected(self):
        for record in ("1,Demo,2026-09-01,1", "1,Demo,2026-09-01,1,USD,extra"):
            with self.subTest(record=record):
                self.write_csv(HEADER + record + "\n")
                with self.assertRaisesRegex(workflow.InputError, "line 2: expected 5 fields"):
                    workflow.read_orders(self.source)

    def test_empty_header_only_and_malformed_csv_fail(self):
        for text in ("", HEADER, HEADER + '1,"Unclosed,2026-09-01,1,USD\n'):
            with self.subTest(text=text):
                self.write_csv(text)
                with self.assertRaises(workflow.InputError):
                    workflow.read_orders(self.source)

    def test_output_cannot_overwrite_input(self):
        original = HEADER + "1,Demo,2026-09-01,1,USD\n"
        self.write_csv(original)
        with self.assertRaisesRegex(workflow.InputError, "different files"):
            workflow.normalize(self.source, self.source)
        self.assertEqual(self.source.read_text(encoding="utf-8"), original)

    def test_failed_replace_keeps_existing_output_and_cleans_temp_file(self):
        self.output.write_text("keep me", encoding="utf-8")
        with mock.patch.object(workflow.os, "replace", side_effect=OSError("simulated replace failure")):
            with self.assertRaisesRegex(OSError, "simulated replace failure"):
                workflow.write_atomic(self.output, {"valid": "payload"})
        self.assertEqual(self.output.read_text(encoding="utf-8"), "keep me")
        self.assertEqual(list(self.directory.glob(".output.json.*.tmp")), [])

    def test_cli_error_is_actionable_without_traceback_or_new_output(self):
        process = subprocess.run(
            [sys.executable, "-B", str(ROOT / "normalize_orders.py"),
             str(ROOT / "examples" / "invalid_orders.csv"), "--output", str(self.output)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(process.returncode, 1)
        self.assertIn("line 3: amount", process.stderr)
        self.assertNotIn("Traceback", process.stderr)
        self.assertFalse(self.output.exists())

    def test_bad_encoding_gets_a_clean_cli_failure(self):
        self.source.write_bytes(b"\xff\xfe invalid UTF-8")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = workflow.main([str(self.source), "--output", str(self.output)])
        self.assertEqual(code, 1)
        self.assertIn("Import failed:", stderr.getvalue())
        self.assertFalse(self.output.exists())

    def test_repeat_run_is_deterministic_and_cli_succeeds(self):
        source = ROOT / "examples" / "orders.csv"
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = workflow.main([str(source), "--output", str(self.output)])
        self.assertEqual(code, 0)
        self.assertIn("Normalized 3 orders", stdout.getvalue())
        first = self.output.read_bytes()
        workflow.normalize(source, self.output)
        self.assertEqual(first, self.output.read_bytes())
        self.assertEqual(list(self.directory.glob(".output.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
