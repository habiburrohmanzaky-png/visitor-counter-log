
"""
Web Visitor Counter Log - Backend REST API (Studi Kasus #5)
Tanpa framework eksternal (menggunakan Python standard library http.server).
Data disimpan di Docker Named Volume: /var/lib/backend_data/visitor_logs.json
"""

import json
import os
import sys
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
DATA_DIR = os.environ.get("DATA_DIR", "/var/lib/backend_data")
DATA_FILE = os.path.join(
    DATA_DIR,
    os.environ.get("DATA_FILE", "visitor_logs.json")
)
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")

MAX_BODY_BYTES = 16 * 1024
MAX_FIELD_LEN = 200

_lock = threading.Lock()


def ensure_storage():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(DATA_FILE):
        write_logs([])


def read_logs():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, list) else []

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def write_logs(logs):
    tmp_path = DATA_FILE + ".tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, DATA_FILE)


def build_summary(logs):
    pages = {}

    for entry in logs:
        page = entry.get("page", "/")
        pages[page] = pages.get(page, 0) + 1

    unique_visitors = len({
        entry.get("visitor", "anonymous")
        for entry in logs
    })

    return {
        "total_hits": len(logs),
        "unique_visitors": unique_visitors,
        "hits_per_page": dict(
            sorted(
                pages.items(),
                key=lambda item: item[1],
                reverse=True
            )
        ),
        "logs": logs,
    }


class VisitorLogHandler(BaseHTTPRequestHandler):

    server_version = "VisitorLogAPI/1.0"

    def _send_json(self, status, payload):
        body = json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, DELETE, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )
        self.end_headers()

        if status != HTTPStatus.NO_CONTENT:
            self.wfile.write(body)

    def _send_error(self, status, message):
        self._send_json(
            status,
            {
                "error": message,
                "status": int(status)
            }
        )

    def _route(self):
        parsed = urlparse(self.path)

        return (
            parsed.path.rstrip("/") or "/",
            parse_qs(parsed.query)
        )

    def _client_ip(self):
        forwarded = self.headers.get("X-Forwarded-For")

        return (
            forwarded.split(",")[0].strip()
            if forwarded
            else self.client_address[0]
        )

    def log_message(self, fmt, *args):
        sys.stdout.write(
            f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] "
            f"{self._client_ip()} - {fmt % args}\n"
        )
        sys.stdout.flush()

    def do_OPTIONS(self):
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self):
        path, _ = self._route()

        if path == "/health":
            return self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "version": APP_VERSION,
                    "storage": DATA_FILE,
                }
            )

        if path == "/logs":
            with _lock:
                logs = read_logs()

            return self._send_json(
                HTTPStatus.OK,
                build_summary(logs)
            )

        self._send_error(
            HTTPStatus.NOT_FOUND,
            f"Endpoint '{path}' tidak ditemukan"
        )

    def do_POST(self):
        path, _ = self._route()

        if path != "/logs":
            return self._send_error(
                HTTPStatus.NOT_FOUND,
                f"Endpoint '{path}' tidak ditemukan"
            )

        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Content-Length tidak valid"
            )

        if length <= 0 or length > MAX_BODY_BYTES:
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Body request kosong atau terlalu besar"
            )

        try:
            payload = json.loads(
                self.rfile.read(length).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Format JSON tidak valid"
            )

        if not isinstance(payload, dict):
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Body JSON harus berupa object"
            )

        page = payload.get("page")

        if not isinstance(page, str) or not page.strip():
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Field 'page' wajib diisi (string)"
            )

        visitor = payload.get("visitor") or "anonymous"

        if not isinstance(visitor, str):
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Field 'visitor' harus berupa string"
            )

        if len(page) > MAX_FIELD_LEN or len(visitor) > MAX_FIELD_LEN:
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Panjang field melebihi batas 200 karakter"
            )

        entry = {
            "page": page.strip(),
            "visitor": visitor.strip(),
            "ip": self._client_ip(),
            "user_agent": (
                self.headers.get("User-Agent") or "unknown"
            )[:MAX_FIELD_LEN],
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(timespec="seconds"),
        }

        with _lock:
            logs = read_logs()
            logs.append(entry)
            write_logs(logs)
            total = len(logs)

        self._send_json(
            HTTPStatus.CREATED,
            {
                "message": "Log kunjungan berhasil disimpan",
                "index": total - 1,
                "total_hits": total,
                "data": entry,
            }
        )

    def do_DELETE(self):
        path, query = self._route()

        if path != "/logs":
            return self._send_error(
                HTTPStatus.NOT_FOUND,
                f"Endpoint '{path}' tidak ditemukan"
            )

        if "index" not in query:
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Query parameter 'index' wajib diisi, misal: /logs?index=0"
            )

        try:
            index = int(query["index"][0])
        except ValueError:
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Parameter 'index' harus berupa bilangan bulat"
            )

        if index < 0:
            return self._send_error(
                HTTPStatus.BAD_REQUEST,
                "Parameter 'index' tidak boleh negatif"
            )

        with _lock:
            logs = read_logs()

            if index >= len(logs):
                return self._send_error(
                    HTTPStatus.NOT_FOUND,
                    f"Index {index} tidak ditemukan (total log: {len(logs)})"
                )

            removed = logs.pop(index)
            write_logs(logs)
            total = len(logs)

        self._send_json(
            HTTPStatus.OK,
            {
                "message": f"Log pada index {index} berhasil dihapus",
                "total_hits": total,
                "deleted": removed,
            }
        )


if __name__ == "__main__":
    ensure_storage()

    server = ThreadingHTTPServer(
        (HOST, PORT),
        VisitorLogHandler
    )

    print(
        f"[BACKEND] Listening on {HOST}:{PORT} | Storage: {DATA_FILE}",
        flush=True
    )

    server.serve_forever()
