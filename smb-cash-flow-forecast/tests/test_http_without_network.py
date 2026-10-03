"""Exercise real HTTP parsing and handlers using an in-memory socket boundary."""

from io import BytesIO
import json
from types import SimpleNamespace
import unittest

from smb_forecast.server import DashboardHandler


class MemoryConnection:
    def __init__(self, request):
        self.input = BytesIO(request)
        self.output = bytearray()

    def makefile(self, *args, **kwargs):
        return self.input

    def sendall(self, data):
        self.output.extend(data)

    def settimeout(self, value):
        pass


def request(method="POST", path="/api/forecast", payload=b"{}", headers=None):
    fields = {"Host": "127.0.0.1:8765", "Content-Type": "application/json",
              "Origin": "http://127.0.0.1:8765", "Content-Length": str(len(payload))}
    fields.update(headers or {})
    source = f"{method} {path} HTTP/1.0\r\n" + "".join(f"{k}: {v}\r\n" for k, v in fields.items()) + "\r\n"
    connection = MemoryConnection(source.encode()+payload)
    DashboardHandler(connection, ("127.0.0.1", 1), SimpleNamespace(server_port=8765))
    head, body = bytes(connection.output).split(b"\r\n\r\n", 1)
    return int(head.split(b" ")[1]), head.decode(), body


class HandlerTests(unittest.TestCase):
    def test_real_http_parser_and_forecast_response(self):
        code, head, body = request()
        self.assertEqual(code, 200)
        self.assertIn("Cache-Control: no-store", head)
        self.assertEqual(len(json.loads(body)["scenarios"]["base"]["months"]), 12)

    def test_assets_and_report(self):
        for path in ("/", "/app.js", "/style.css", "/api/sample"):
            self.assertEqual(request("GET", path)[0], 200)
        code, head, body = request(path="/api/report")
        self.assertEqual(code, 200)
        self.assertIn("text/html", head)
        self.assertIn(b"<!doctype html>", body)

    def test_validation_and_trust_boundaries(self):
        cases = [(b"{}", {"Host": "untrusted.example"}, 403),
                 (b"{}", {"Origin": "https://untrusted.example"}, 403),
                 (b"{}", {"Content-Type": "text/plain"}, 415),
                 (b"{}", {"Content-Length": "131073"}, 413),
                 (b"{bad}", {}, 400), (b'{"a":1,"a":2}', {}, 400),
                 (b'{"assumptions":{"months":61}}', {}, 400)]
        for body, headers, expected in cases:
            with self.subTest(headers=headers, body=body):
                self.assertEqual(request(payload=body, headers=headers)[0], expected)

    def test_paths_cannot_read_local_files(self):
        for path in ("/../README.md", "/.env", "/api/files"):
            self.assertEqual(request("GET", path)[0], 404)


if __name__ == "__main__":
    unittest.main()
