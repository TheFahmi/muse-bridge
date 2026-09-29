#!/usr/bin/env python3
"""Muse bridge: OpenAI-compatible endpoint on VPS localhost.
9Router 'Muse' provider -> http://127.0.0.1:8765/v1
Requests are queued; the Muse agent (sandbox) polls pending/ and writes answers to done/.

v2: threaded server (one slow chat request must not block /health or /v1/models),
per-connection socket timeout, BrokenPipe-safe sends.
"""
import json, os, time, uuid, socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = "/home/ubuntu/muse-bridge/queue"
PENDING = f"{BASE}/pending"
DONE = f"{BASE}/done"
MAX_PENDING = 5
WAIT_SECS = 110

class H(BaseHTTPRequestHandler):
    timeout = 120  # per-socket-op timeout: slow-loris bodies can't wedge a thread forever
    def log_message(self, *a):
        pass
    def _send(self, code, obj, ctype="application/json"):
        try:
            body = obj.encode() if isinstance(obj, str) else json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass  # client went away; nothing to do
    def do_GET(self):
        try:
            if self.path.rstrip("/") == "/v1/models":
                self._send(200, {"object": "list", "data": [
                    {"id": "muse", "object": "model", "created": 0, "owned_by": "muse"}]})
            elif self.path == "/health":
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:
            try:
                self._send(500, {"error": {"message": str(e)[:200]}})
            except Exception:
                pass
    def do_POST(self):
        try:
            if self.path.rstrip("/") != "/v1/chat/completions":
                return self._send(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                return self._send(400, {"error": {"message": "bad json"}})
            try:
                npend = len(os.listdir(PENDING))
            except Exception:
                npend = 0
            if npend >= MAX_PENDING:
                return self._send(429, {"error": {"message": "Muse bridge busy, try again in a bit"}})
            rid = uuid.uuid4().hex
            with open(f"{PENDING}/{rid}.json", "w") as f:
                json.dump({"id": rid, "received_at": time.time(), "request": req}, f)
            deadline = time.time() + WAIT_SECS
            answer = None
            while time.time() < deadline:
                dp = f"{DONE}/{rid}.json"
                if os.path.exists(dp):
                    try:
                        with open(dp) as f:
                            answer = json.load(f).get("content", "")
                    except Exception:
                        answer = ""
                    try:
                        os.remove(dp)
                    except Exception:
                        pass
                    break
                time.sleep(1)
            try:
                os.remove(f"{PENDING}/{rid}.json")
            except Exception:
                pass
            if answer is None:
                return self._send(504, {"error": {"message": "Muse did not answer in time"}})
            cid = "chatcmpl-" + uuid.uuid4().hex[:12]
            created = int(time.time())
            if req.get("stream"):
                chunk1 = {"id": cid, "object": "chat.completion.chunk", "created": created,
                          "model": "muse", "choices": [{"index": 0,
                          "delta": {"role": "assistant", "content": answer}, "finish_reason": None}]}
                chunk2 = {"id": cid, "object": "chat.completion.chunk", "created": created,
                          "model": "muse", "choices": [{"index": 0, "delta": {},
                          "finish_reason": "stop"}]}
                sse = "data: " + json.dumps(chunk1) + "\n\ndata: " + json.dumps(chunk2) + "\n\ndata: [DONE]\n\n"
                return self._send(200, sse, "text/event-stream")
            resp = {"id": cid, "object": "chat.completion", "created": created, "model": "muse",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": answer},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
            self._send(200, resp)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            pass
        except Exception as e:
            try:
                self._send(500, {"error": {"message": str(e)[:200]}})
            except Exception:
                pass

if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 8765), H)
    srv.daemon_threads = True
    srv.allow_reuse_address = True
    srv.serve_forever()
