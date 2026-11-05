import json, os, shutil, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

OK_BODY = b'{"choices":[{"message":{"content":"resposta do modelo"}}]}'

class TempRootCase(unittest.TestCase):
    """Cada teste roda em uma pasta com espaço e acento, como o Neku precisa suportar."""
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="neko teste ação "))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def write_settings(self, content):
        path = self.root / "config" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            content = json.dumps(content).encode()
        path.write_bytes(content)
        return path

class FakeServer:
    """Servidor local que responde como um llama-server e guarda o que recebeu."""
    def __init__(self, body=OK_BODY, status=200, delay=0, headers=()):
        self.body, self.status, self.delay, self.headers = body, status, delay, headers
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self):
                time.sleep(outer.delay)
                self.send_response(outer.status)
                for name, value in outer.headers:
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(outer.body)))
                self.end_headers()
                self.wfile.write(outer.body)

            def do_POST(self):
                size = int(self.headers.get("content-length", 0))
                outer.requests.append(json.loads(self.rfile.read(size)))
                self.respond()

            def do_GET(self):
                outer.requests.append(None)
                self.respond()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/chat/completions"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
