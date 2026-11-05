import json, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest import mock
from helpers import FakeServer, TempRootCase
from neko.config import Config
from neko.llm import LocalLLM, _read_stream, fit_messages
from neko.runtime import LOW_PRIORITY, ModelRuntime

FAKE_SERVER = '''
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"ok")
    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length", 0)))
        body = b\'{"choices":[{"message":{"content":"oi do servidor"}}]}\'
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
'''

class RuntimeCase(TempRootCase):
    def setUp(self):
        super().setUp()
        self.config = Config(self.root)
        self.runtime = ModelRuntime(self.root, self.config)
        self.addCleanup(self.runtime.stop)

    def install(self):
        (self.root / "runtime" / "llama").mkdir(parents=True, exist_ok=True)
        self.runtime.exe.write_bytes(b"")
        (self.root / "models").mkdir(exist_ok=True)
        (self.root / "models" / "modelo.gguf").write_bytes(b"")
        script = self.root / "servidor.py"
        script.write_text(FAKE_SERVER, encoding="utf-8")
        self.runtime.command = lambda port: [sys.executable, str(script), str(port)]

class RuntimeTests(RuntimeCase):
    def test_not_available_without_files(self):
        self.assertFalse(self.runtime.available())

    def test_not_available_without_a_model(self):
        (self.root / "runtime" / "llama").mkdir(parents=True)
        self.runtime.exe.write_bytes(b"")
        self.assertFalse(self.runtime.available())

    def test_binds_only_to_loopback_with_the_configured_context(self):
        (self.root / "models").mkdir()
        (self.root / "models" / "modelo.gguf").write_bytes(b"")
        command = ModelRuntime(self.root, self.config).command(8123)
        self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
        self.assertEqual(command[command.index("-c") + 1], "2048")

    def test_default_is_four_threads_at_low_priority(self):
        (self.root / "models").mkdir()
        (self.root / "models" / "modelo.gguf").write_bytes(b"")
        command = ModelRuntime(self.root, self.config).command(8123)
        self.assertEqual(command[command.index("-t") + 1], "4")
        self.assertEqual(subprocess.BELOW_NORMAL_PRIORITY_CLASS, LOW_PRIORITY)
        self.install()
        with mock.patch("subprocess.Popen", side_effect=OSError()) as started, self.assertLogs("neko.runtime", level="ERROR"):
            self.runtime.ensure()
        self.assertTrue(started.call_args.kwargs["creationflags"] & LOW_PRIORITY)

    def test_starts_on_demand_and_reuses(self):
        self.install()
        self.assertFalse(self.runtime.running())
        url = self.runtime.ensure()
        self.assertTrue(url.startswith("http://127.0.0.1:"))
        self.assertEqual(self.runtime.ensure(), url)

    def test_answers_through_the_bundled_server(self):
        self.install()
        self.assertEqual(LocalLLM(self.config, self.runtime).reply("s", [{"role":"user","content":"oi"}]), "oi do servidor")

    def test_unloads_when_idle(self):
        self.install()
        self.runtime.ensure()
        self.runtime.stop_if_idle()
        self.assertTrue(self.runtime.running())
        self.runtime.last_used -= 3600
        self.runtime.stop_if_idle()
        self.assertFalse(self.runtime.running())

    def test_restarts_after_unloading(self):
        self.install()
        self.runtime.ensure()
        self.runtime.stop()
        self.assertIsNotNone(self.runtime.ensure())

    def loading(self):
        """Um servidor que nunca fica pronto, como o modelo carregando do disco pela primeira vez."""
        self.install()
        self.spawned = []
        self.runtime.command = lambda port: self.spawned.append(port) or [sys.executable, "-c", "import time; time.sleep(60)"]
        patcher = mock.patch("neko.runtime.START_TIMEOUT", 8)
        patcher.start()
        self.addCleanup(patcher.stop)
        worker = threading.Thread(target=self.runtime.ensure, daemon=True)
        worker.start()
        limit = time.monotonic() + 5
        while time.monotonic() < limit and not self.runtime.running():
            time.sleep(0.01)
        self.assertTrue(self.runtime.running())
        return worker

    def test_closing_does_not_wait_for_the_model_to_load(self):
        worker = self.loading()
        started = time.monotonic()
        self.runtime.stop()
        self.assertLess(time.monotonic() - started, 3)
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(self.runtime.running())

    def test_idle_check_never_holds_the_interface(self):
        self.loading()
        started = time.monotonic()
        self.runtime.stop_if_idle()
        self.assertLess(time.monotonic() - started, 2)
        self.assertTrue(self.runtime.running())

    def test_request_in_line_gives_up_when_stopped(self):
        worker = self.loading()
        answers = []
        waiting = threading.Thread(target=lambda: answers.append(self.runtime.ensure()), daemon=True)
        waiting.start()
        time.sleep(0.1)
        self.runtime.stop()
        worker.join(3)
        waiting.join(3)
        self.assertFalse(waiting.is_alive())
        self.assertEqual(answers, [None])
        self.assertEqual(len(self.spawned), 1)
        self.assertFalse(self.runtime.running())

    def test_starts_again_after_a_cancelled_load(self):
        self.loading()
        self.runtime.stop()
        self.install()
        with mock.patch("neko.runtime.START_TIMEOUT", 60):
            self.assertIsNotNone(self.runtime.ensure())

    def test_server_that_fails_to_start_means_basic_mode(self):
        self.install()
        self.runtime.command = lambda port: [sys.executable, "-c", "raise SystemExit(1)"]
        self.assertIsNone(self.runtime.ensure())
        self.assertIsNone(LocalLLM(self.config, self.runtime).reply("s", [{"role":"user","content":"oi"}]))

    def test_missing_executable_means_basic_mode(self):
        self.install()
        self.runtime.command = lambda port: [str(self.root / "nao existe.exe")]
        with self.assertLogs("neko.runtime", level="ERROR"):
            self.assertIsNone(self.runtime.ensure())

    def test_bundled_model_can_be_disabled(self):
        self.install()
        self.config.data["llm"]["use_bundled"] = False
        self.assertFalse(LocalLLM(self.config, self.runtime).enabled())

class FitTests(TempRootCase):
    def test_oldest_messages_go_first(self):
        messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}" + "x" * 800} for i in range(7)]
        kept = fit_messages(messages, "s", 700)
        self.assertEqual(kept[-1]["content"], messages[-1]["content"])
        self.assertLess(len(kept), 6)
        self.assertEqual(kept[0]["role"], "user")

    def test_huge_prompt_never_drops_your_message(self):
        kept = fit_messages([{"role":"user","content":"o que é a lua?"}], "x" * 9000, 512)
        self.assertEqual([m["content"] for m in kept], ["o que é a lua?"])

    def test_very_long_message_is_cut(self):
        kept = fit_messages([{"role":"user","content":"x" * 9000}], "s", 2048)
        self.assertEqual(len(kept[0]["content"]), 1000)

    def test_no_room_still_sends_the_last_message(self):
        kept = fit_messages([{"role":"user","content":"x" * 900}], "s", 200)
        self.assertEqual(len(kept), 1)
        self.assertLess(len(kept[0]["content"]), 900)

class StreamTests(TempRootCase):
    def lines(self, *events):
        return [f"data: {event}\n".encode() for event in events]

    def test_tokens_arrive_in_order(self):
        tokens = []
        chunk = lambda text: json.dumps({"choices":[{"delta":{"content":text}}]})
        result = _read_stream(self.lines(chunk("Oi"), chunk(" você"), "[DONE]"), tokens.append)
        self.assertEqual(tokens, ["Oi", " você"])
        self.assertEqual(result, "Oi você")

    def test_cut_stream_ends_on_a_complete_sentence(self):
        events = [json.dumps({"choices":[{"delta":{"content":"Frase um. Frase do"},"finish_reason":None}]}),
                  json.dumps({"choices":[{"delta":{},"finish_reason":"length"}]})]
        self.assertEqual(_read_stream(self.lines(*events), lambda token: None), "Frase um.")

    def test_broken_events_are_skipped(self):
        tokens = []
        good = json.dumps({"choices":[{"delta":{"content":"ok"}}]})
        self.assertEqual(_read_stream(self.lines("{quebrado", '{"choices":[]}', "null", good), tokens.append), "ok")

    def test_real_stream_over_http(self):
        body = b"".join(f"data: {json.dumps({'choices':[{'delta':{'content':t}}]})}\n\n".encode() for t in ("um ", "dois"))
        server = FakeServer(body=body + b"data: [DONE]\n\n")
        self.addCleanup(server.close)
        config = Config(self.root)
        config.data["llm"].update(enabled=True, endpoint=server.url)
        tokens = []
        reply = LocalLLM(config).reply("s", [{"role":"user","content":"oi"}], tokens.append)
        self.assertEqual(reply, "um dois")
        self.assertEqual(tokens, ["um ", "dois"])
        self.assertIs(server.requests[0]["stream"], True)
