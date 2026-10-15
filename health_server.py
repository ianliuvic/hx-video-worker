"""Health endpoint + daily video trigger for the hx-video-worker container.

Replaces the old in-container cron: the Coolify scheduler (via the dsh worker)
POSTs /run each morning; this process spawns make_daily_videos.py with the
container's full environment, so credentials are always available.

Auth: Authorization: Bearer $VIDEO_WORKER_TOKEN on POST /run and GET /status.
Idempotency: a completed run for today (Asia/Shanghai) makes further /run calls
return {"skipped": true}; pass ?force=1 for a deliberate re-run.
"""

import datetime
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

APP = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(APP, "output")
STATE_PATH = os.path.join(OUT, ".state.json")
TOKEN = os.environ.get("VIDEO_WORKER_TOKEN", "").strip()
TZ = datetime.timezone(datetime.timedelta(hours=8))

_lock = threading.Lock()
_running = {"proc": None}


def _now():
    return datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def _today():
    return datetime.datetime.now(TZ).date().isoformat()


def _read_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def _write_state(state):
    os.makedirs(OUT, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=1)


def _run_batch():
    os.makedirs(OUT, exist_ok=True)
    log_path = os.path.join(OUT, time.strftime("run-%Y%m%d-%H%M%S.log"))
    state = {"date": _today(), "status": "running", "started_at": _now(), "log": log_path}
    _write_state(state)
    try:
        with open(log_path, "ab") as logf:
            rc = subprocess.call(
                ["python3", os.path.join(APP, "make_daily_videos.py")],
                cwd=APP, stdout=logf, stderr=subprocess.STDOUT,
            )
        state.update({
            "status": "done" if rc == 0 else "failed",
            "exit_code": rc,
            "finished_at": _now(),
        })
    except Exception as exc:  # noqa: BLE001
        state.update({"status": "failed", "error": str(exc)[:300], "finished_at": _now()})
    finally:
        _write_state(state)
        with _lock:
            _running["proc"] = None


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        if not TOKEN:
            return False
        header = self.headers.get("Authorization", "")
        return header == "Bearer " + TOKEN

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/health"):
            return self._json(200, {"ok": True, "service": "hx-video-worker", "state": _read_state().get("status", "idle")})
        if path == "/status":
            if not self._authorized():
                return self._json(401, {"ok": False, "error": "unauthorized"})
            with _lock:
                running = bool(_running["proc"])
            return self._json(200, {"ok": True, "running": running, "last_run": _read_state()})
        return self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        path, _, query = self.path.partition("?")
        if path != "/run":
            return self._json(404, {"ok": False, "error": "not found"})
        if not self._authorized():
            return self._json(401, {"ok": False, "error": "unauthorized"})
        force = "force=1" in query

        with _lock:
            if _running["proc"] is not None:
                return self._json(409, {"ok": False, "running": True, "error": "a run is already in progress"})

            state = _read_state()
            if not force and state.get("date") == _today() and state.get("status") == "done":
                return self._json(200, {"ok": True, "skipped": True, "reason": "already ran today", "last_run": state})

            proc = threading.Thread(target=_run_batch, name="video-batch", daemon=True)
            proc.start()
            _running["proc"] = proc

        return self._json(202, {"ok": True, "started": True, "date": _today()})

    def log_message(self, *args):  # silence access logs
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3010"))
    print(f"hx-video-worker listening on :{port} (token {'set' if TOKEN else 'MISSING'})", flush=True)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
