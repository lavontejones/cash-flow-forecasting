"""CLI exports, escaped reporting, and local API trust boundaries."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from smb_forecast.__main__ import main
from smb_forecast.model import dumps, loads, run_model
from smb_forecast.report import csv_output, report_html
from smb_forecast.server import make_server

ROOT = Path(__file__).resolve().parents[1]


class ExportTests(unittest.TestCase):
    def test_cli_complete_exports_and_validation(self):
        with tempfile.TemporaryDirectory() as path, redirect_stdout(StringIO()):
            target = Path(path)
            source = ROOT / "examples/sample-business.json"
            self.assertEqual(main(["validate", str(source)]), 0)
            self.assertEqual(main(["forecast", str(source), "--out", str(target)]), 0)
            self.assertEqual({p.name for p in target.iterdir()},
                             {"base.csv", "downside.csv", "upside.csv", "custom.csv", "forecast.json", "report.html"})
            model = run_model(loads(source.read_text()))
            self.assertEqual(json.loads((target/"forecast.json").read_text()), json.loads(dumps(model)))

    def test_cli_error_is_actionable(self):
        with redirect_stderr(StringIO()) as stream:
            self.assertEqual(main(["validate", "/nonexistent/assumptions.json"]), 2)
        self.assertIn("Error:", stream.getvalue())

    def test_report_escapes_model_name_and_hire_metadata(self):
        model = run_model({"model_name": '<script>alert("x")</script>', "assumptions": {
            "hires": [{"name": '<img src=x onerror=alert(1)>', "start_month": "2027-01", "monthly_cost": 1}]}})
        html = report_html(model)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)
        self.assertNotIn("https://", html)

    def test_csv_contains_all_core_calculations(self):
        result = run_model({})["scenarios"]["base"]
        csv = csv_output(result)
        self.assertIn("cash_reconciliation_difference", csv)
        self.assertIn("cash_runway_months", csv)
        self.assertIn("ending_ar", csv)
        self.assertEqual(len(csv.splitlines()), 13)

    def test_committed_outputs_are_reproducible(self):
        model = run_model(loads((ROOT/"examples/sample-business.json").read_text()))
        self.assertEqual((ROOT/"examples/outputs/forecast.json").read_text(), dumps(model, indent=2)+"\n")
        self.assertEqual((ROOT/"examples/outputs/report.html").read_text(), report_html(model))
        for name, result in model["scenarios"].items():
            with (ROOT/"examples/outputs"/f"{name}.csv").open(newline="") as file:
                self.assertEqual(file.read(), csv_output(result))


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def post(self, path="/api/forecast", body=b"{}", headers=None):
        merged = {"Content-Type": "application/json", "Origin": self.url}
        merged.update(headers or {})
        return urlopen(Request(self.url+path, data=body, headers=merged), timeout=5)

    def test_page_assets_and_api(self):
        for path in ("/", "/app.js", "/style.css", "/api/sample"):
            with urlopen(self.url+path, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        with self.post() as response:
            model = json.load(response)
        self.assertEqual(len(model["scenarios"]["base"]["months"]), 12)
        with self.post("/api/report") as response:
            self.assertIn(b"<!doctype html>", response.read())

    def test_invalid_json_and_model(self):
        for payload in (b'{bad}', b'{"assumptions":{"tax_rate":2}}', b'{"a":1,"a":2}'):
            with self.subTest(payload=payload), self.assertRaises(HTTPError) as error:
                self.post(body=payload)
            self.assertEqual(error.exception.code, 400)

    def test_origin_host_content_type_and_body_limits(self):
        cases = [(b"{}", {"Origin": "https://untrusted.example"}, 403),
                 (b"{}", {"Host": "untrusted.example"}, 403),
                 (b"{}", {"Content-Type": "text/plain"}, 415),
                 (b"x" * (128*1024+1), {}, 413)]
        for body, headers, code in cases:
            with self.subTest(code=code, headers=headers), self.assertRaises(HTTPError) as error:
                self.post(body=body, headers=headers)
            self.assertEqual(error.exception.code, code)

    def test_no_file_or_traversal_api(self):
        for path in ("/../README.md", "/api/file", "/.env", "/favicon.ico"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(self.url+path, timeout=5)
            self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
