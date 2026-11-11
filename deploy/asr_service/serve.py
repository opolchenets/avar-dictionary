"""Private, single-inference HTTP service. Publish through authenticated Django only."""
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bundle import MAX_PCM_BYTES, Recognizer, validate_pcm


def make_handler(recognizer, token):
    if len(token) < 32:
        raise ValueError("ASR_INTERNAL_TOKEN must contain at least 32 characters")
    gate = threading.BoundedSemaphore(1)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass  # Never log request audio, Authorization headers or transcripts.

        def reply(self, code, body):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            return hmac.compare_digest(self.headers.get("Authorization", "").encode(),
                                       ("Bearer " + token).encode())

        def do_GET(self):
            if not self.authorized():
                return self.reply(401, {"error": "unauthorized"})
            if self.path != "/health":
                return self.reply(404, {"error": "not_found"})
            self.reply(200, {"ready": True, "version": recognizer.manifest["version"], "max_seconds": 10})

        def do_POST(self):
            if not self.authorized():
                return self.reply(401, {"error": "unauthorized"})
            if self.path != "/transcribe":
                return self.reply(404, {"error": "not_found"})
            if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type") != "audio/pcm":
                return self.reply(400, {"error": "expected_pcm16_mono_16000"})
            lengths = self.headers.get_all("Content-Length", [])
            try:
                if len(lengths) != 1:
                    raise ValueError()
                length = int(lengths[0])
                if not 3200 <= length <= MAX_PCM_BYTES or length % 2:
                    raise ValueError()
            except ValueError:
                return self.reply(413, {"error": "audio_must_be_0.1_to_10_seconds"})
            if not gate.acquire(blocking=False):
                return self.reply(503, {"error": "busy"})
            try:
                pcm = self.rfile.read(length)
                if len(pcm) != length:
                    return self.reply(400, {"error": "incomplete_audio"})
                validate_pcm(pcm)
                text = recognizer.transcribe(pcm)
                self.reply(200, {"text": text, "version": recognizer.manifest["version"]})
            except (BrokenPipeError, ConnectionError, TimeoutError):
                pass
            except Exception:
                self.reply(503, {"error": "recognition_failed"})
            finally:
                gate.release()

    return Handler


if __name__ == "__main__":
    secret = os.environ.get("ASR_INTERNAL_TOKEN", "")
    if len(secret) < 32:
        raise SystemExit("Set a private ASR_INTERNAL_TOKEN with at least 32 characters")
    engine = Recognizer(os.getenv("ASR_MODEL_DIR", "/models"))
    server = ThreadingHTTPServer(("0.0.0.0", 8090), make_handler(engine, secret))
    server.daemon_threads = True
    print("READY", engine.manifest["version"], flush=True)
    server.serve_forever()
