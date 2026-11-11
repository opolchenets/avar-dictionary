import hashlib
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from http.server import ThreadingHTTPServer

from bundle import MAX_PCM_BYTES, validate_pcm, verify_bundle
from serve import make_handler


class BundleTests(unittest.TestCase):
    def test_pcm_ten_second_boundary(self):
        validate_pcm(b"\0" * MAX_PCM_BYTES)
        for pcm in (b"", b"\0" * 3198, b"\0" * (MAX_PCM_BYTES + 2), b"\0" * 3201):
            with self.assertRaises(ValueError):
                validate_pcm(pcm)

    def test_missing_corrupt_and_escaping_files_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = ["model/config.json", "model/model.safetensors", "model/preprocessor_config.json",
                     "model/tokenizer_config.json", "model/vocab.json", "avar_4gram.bin", "unigrams.txt"]
            for name in names:
                p = root / name
                p.parent.mkdir(exist_ok=True)
                p.write_bytes(b"example")
            files = {name: hashlib.sha256(b"example").hexdigest() for name in names}
            manifest = {"format": 1, "language": "ava", "version": "test", "files": files}
            (root / "manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(verify_bundle(root)["version"], "test")
            (root / "unigrams.txt").write_text("changed")
            with self.assertRaises(ValueError):
                verify_bundle(root)
            files["../outside"] = "0" * 64
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                verify_bundle(root)

    def test_private_api_auth_limits_and_no_model_download(self):
        called = []
        engine = SimpleNamespace(manifest={"version": "test"},
                                 transcribe=lambda pcm: called.append(pcm) or "Текст")
        token = "s" * 40
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(engine, token))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(path, body=b"\0" * 3200, auth=token):
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            connection.request("POST", path, body=body,
                headers={"Authorization": "Bearer " + auth, "Content-Type": "audio/pcm"})
            response = connection.getresponse()
            code, data = response.status, json.loads(response.read())
            connection.close()
            return code, data

        try:
            self.assertEqual(request("/transcribe", auth="wrong")[0], 401)
            self.assertEqual(request("/model/model.safetensors")[0], 404)
            self.assertEqual(request("/transcribe", b"\0" * (MAX_PCM_BYTES + 2))[0], 413)
            code, body = request("/transcribe")
            self.assertEqual((code, body["text"], body["version"]), (200, "Текст", "test"))
            self.assertEqual(len(called), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
