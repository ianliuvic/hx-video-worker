"""Tiny health endpoint so Coolify can monitor the worker container."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"ok": True, "service": "hx-video-worker"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3010"))
    print(f"health server on :{port}")
    HTTPServer(("0.0.0.0", port), H).serve_forever()
