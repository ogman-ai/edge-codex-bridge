import argparse
import http.server
import json
import os
import queue
import secrets
import socket
import struct
import sys
import tempfile
import threading
import time
import urllib.parse


HOST = "127.0.0.1"
DEFAULT_PORT = 47365
STATE_PATH = os.path.join(tempfile.gettempdir(), "edge-codex-bridge-state.json")
MAX_RECENT_EVENTS = 100


class Bridge:
    def __init__(self, token):
        self.token = token
        self.next_id = 1
        self.pending = {}
        self.pending_lock = threading.Lock()
        self.write_lock = threading.Lock()
        self.events = []
        self.events_lock = threading.Lock()
        self.closed = False

    def log(self, message):
        print(f"[edge-codex-bridge] {message}", file=sys.stderr, flush=True)

    def send_message(self, message):
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        frame = struct.pack("<I", len(payload)) + payload
        with self.write_lock:
            sys.stdout.buffer.write(frame)
            sys.stdout.buffer.flush()

    def send_response(self, request_id, result=None, error=None):
        if error is None:
            self.send_message({"jsonrpc": "2.0", "id": request_id, "result": result})
        else:
            self.send_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": 1, "message": str(error)},
                }
            )

    def request(self, method, params=None, timeout=10):
        if self.closed:
            raise RuntimeError("native host is closed")
        with self.pending_lock:
            request_id = self.next_id
            self.next_id += 1
            response_queue = queue.Queue(maxsize=1)
            self.pending[request_id] = response_queue
        try:
            self.send_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params or {},
                }
            )
            try:
                response = response_queue.get(timeout=timeout)
            except queue.Empty as exc:
                raise TimeoutError(f"timed out waiting for RPC method {method}") from exc
            if "error" in response:
                error = response["error"]
                if isinstance(error, dict):
                    raise RuntimeError(error.get("message") or json.dumps(error))
                raise RuntimeError(str(error))
            return response.get("result")
        finally:
            with self.pending_lock:
                self.pending.pop(request_id, None)

    def handle_message(self, message):
        if not isinstance(message, dict):
            self.log("ignored non-object message")
            return

        if "id" in message and "method" not in message:
            with self.pending_lock:
                response_queue = self.pending.get(message["id"])
            if response_queue is not None:
                response_queue.put(message)
            return

        method = message.get("method")
        if method is None:
            return

        if "id" in message:
            try:
                result = self.handle_extension_request(method, message.get("params") or {})
                self.send_response(message["id"], result=result)
            except Exception as exc:
                self.send_response(message["id"], error=exc)
            return

        self.record_event(method, message.get("params"))

    def handle_extension_request(self, method, params):
        if method == "ping":
            return "pong"
        self.record_event(method, params)
        return None

    def record_event(self, method, params):
        event = {"method": method, "params": params, "time": time.time()}
        with self.events_lock:
            self.events.append(event)
            del self.events[:-MAX_RECENT_EVENTS]

    def snapshot_events(self):
        with self.events_lock:
            return list(self.events)

    def clear_events(self):
        with self.events_lock:
            self.events.clear()


def read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


def native_read_loop(bridge):
    while True:
        header = read_exact(sys.stdin.buffer, 4)
        if header is None:
            bridge.closed = True
            bridge.log("stdin closed")
            return
        size = struct.unpack("<I", header)[0]
        payload = read_exact(sys.stdin.buffer, size)
        if payload is None:
            bridge.closed = True
            bridge.log("stdin closed during payload")
            return
        try:
            bridge.handle_message(json.loads(payload.decode("utf-8")))
        except Exception as exc:
            bridge.log(f"failed to handle message: {exc}")


class Handler(http.server.BaseHTTPRequestHandler):
    bridge = None

    def log_message(self, fmt, *args):
        self.bridge.log(fmt % args)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        return self.headers.get("X-Edge-Codex-Bridge-Token") == self.bridge.token

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/health":
            self.send_json(
                200,
                {
                    "ok": True,
                    "closed": self.bridge.closed,
                    "events": self.bridge.snapshot_events()[-10:],
                },
            )
            return
        if parsed.path == "/events":
            if not self.authorized():
                self.send_json(401, {"ok": False, "error": "unauthorized"})
                return
            query = urllib.parse.parse_qs(parsed.query)
            limit = int((query.get("limit") or ["100"])[0])
            method = (query.get("method") or [None])[0]
            events = self.bridge.snapshot_events()
            if method:
                events = [event for event in events if event.get("method") == method]
            self.send_json(200, {"ok": True, "events": events[-limit:]})
            return
        self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self.authorized():
            self.send_json(401, {"ok": False, "error": "unauthorized"})
            return
        if self.path == "/events/clear":
            self.bridge.clear_events()
            self.send_json(200, {"ok": True})
            return
        if self.path != "/rpc":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            method = payload["method"]
            params = payload.get("params") or {}
            timeout = float(payload.get("timeout", 10))
            result = self.bridge.request(method, params=params, timeout=timeout)
            self.send_json(200, {"ok": True, "result": result})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})


def choose_port(start_port):
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError("no free localhost port found")


def write_state(port, token):
    state = {
        "host": HOST,
        "port": port,
        "token": token,
        "pid": os.getpid(),
        "startedAt": time.time(),
    }
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    token = secrets.token_urlsafe(24)
    bridge = Bridge(token)
    port = choose_port(args.port)
    write_state(port, token)

    Handler.bridge = bridge
    server = http.server.ThreadingHTTPServer((HOST, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    bridge.log(f"HTTP bridge listening on {HOST}:{port}")

    try:
        native_read_loop(bridge)
    finally:
        server.shutdown()
        try:
            os.remove(STATE_PATH)
        except OSError:
            pass


if __name__ == "__main__":
    main()
