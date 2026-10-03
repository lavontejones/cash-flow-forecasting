"""Loopback-only dashboard. No cloud calls, uploads, telemetry, or file API."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
import json

from .model import ModelError, dumps, loads, run_model
from .report import report_html

MAX_BODY = 128 * 1024


class DashboardHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass  # Do not log assumption payloads or client-supplied paths.

    def respond(self, status, content, content_type="application/json; charset=utf-8"):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def trusted_request(self, check_origin=False):
        host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != host:
            self.respond(403, json.dumps({"error": "Use the displayed 127.0.0.1 address"}))
            return False
        origin = self.headers.get("Origin")
        if check_origin and origin is not None and origin != f"http://{host}":
            self.respond(403, json.dumps({"error": "Cross-origin requests are blocked"}))
            return False
        return True

    def do_GET(self):
        if not self.trusted_request():
            return
        routes = {"/": ("web/index.html", "text/html; charset=utf-8"),
                  "/app.js": ("web/app.js", "text/javascript; charset=utf-8"),
                  "/style.css": ("web/style.css", "text/css; charset=utf-8"),
                  "/api/sample": ("sample.json", "application/json; charset=utf-8")}
        if self.path not in routes:
            self.respond(404, json.dumps({"error": "Not found"}))
            return
        filename, content_type = routes[self.path]
        content = resources.files("smb_forecast").joinpath(filename).read_text(encoding="utf-8")
        self.respond(200, content, content_type)

    def do_POST(self):
        if not self.trusted_request(check_origin=True):
            return
        if self.path not in ("/api/forecast", "/api/report"):
            self.respond(404, json.dumps({"error": "Not found"}))
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self.respond(415, json.dumps({"error": "Content-Type must be application/json"}))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.respond(413, json.dumps({"error": "Request must contain 1 to 131072 bytes"}))
                return
            document = loads(self.rfile.read(length).decode("utf-8"))
            model = run_model(document)
            if self.path == "/api/report":
                self.respond(200, report_html(model), "text/html; charset=utf-8")
            else:
                self.respond(200, dumps(model))
        except (ModelError, UnicodeError, ValueError, RecursionError) as exc:
            self.respond(400, json.dumps({"error": str(exc)}))


def make_server(port=8765):
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Port must be an integer from 0 to 65535")
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    server.daemon_threads = True
    return server


def serve_dashboard(port=8765):
    server = make_server(port)
    print(f"Dashboard: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
