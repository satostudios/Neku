import os, subprocess, sys, time
from pathlib import Path
import psutil
from helpers import FakeServer, TempRootCase

CHILD = Path(__file__).with_name("lifecycle_child.py")
ENV = {**os.environ, "PYTHONIOENCODING":"utf-8", "PYTHONDONTWRITEBYTECODE":"1"}

class LifecycleTests(TempRootCase):
    def spawn(self, close_after_ms=300, mode="-"):
        process = subprocess.Popen([sys.executable, str(CHILD), str(self.root), str(close_after_ms), mode],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", env=ENV)
        self.addCleanup(process.stdout.close)
        self.addCleanup(self.kill_tree, process)
        return process

    @staticmethod
    def kill_tree(process):
        if process.poll() is not None:
            return
        for proc in psutil.Process(process.pid).children(recursive=True) + [psutil.Process(process.pid)]:
            try:
                proc.kill()
            except psutil.Error:
                pass
        process.wait(10)

    def wait_for(self, process, text):
        lines = []
        for line in process.stdout:
            lines.append(line)
            if text in line:
                return line
        self.fail(f"{text!r} não apareceu: {lines}")

    def test_body_is_the_small_one(self):
        process = self.spawn()
        self.assertIn("ABERTO 48.0", self.wait_for(process, "ABERTO"))
        self.assertEqual(process.wait(15), 0)

    def test_opens_and_closes_cleanly(self):
        process = self.spawn()
        stamp = float(self.wait_for(process, "FECHANDO").split()[1])
        self.assertEqual(process.wait(10), 0)
        self.assertLess(time.time() - stamp, 2)
        self.assertFalse((self.root / "data" / "neko.lock").exists())
        self.assertTrue((self.root / "data" / "memory" / "identity.md").exists())
        self.assertIn("Neku encerrado", (self.root / "child.log").read_text(encoding="utf-8"))

    def test_second_instance_does_not_open(self):
        first = self.spawn(close_after_ms=300000)
        self.wait_for(first, "ABERTO")
        second = self.spawn()
        output = second.communicate(timeout=120)[0]
        self.assertEqual(second.returncode, 0)
        self.assertIn("já está aberto", output)
        self.assertNotIn("ABERTO", output)
        self.assertIsNone(first.poll())

    def test_opens_again_after_a_crash(self):
        first = self.spawn(close_after_ms=15000)
        self.wait_for(first, "ABERTO")
        self.kill_tree(first)
        second = self.spawn()
        self.wait_for(second, "ABERTO")
        self.assertEqual(second.wait(15), 0)

    def test_quit_does_not_wait_for_a_pending_answer(self):
        server = FakeServer(delay=30)
        self.addCleanup(server.close)
        self.write_settings({"llm": {"enabled": True, "endpoint": server.url, "timeout_seconds": 120}})
        process = self.spawn(close_after_ms=800, mode="chat")
        stamp = float(self.wait_for(process, "FECHANDO").split()[1])
        self.assertEqual(process.wait(10), 0)
        self.assertLess(time.time() - stamp, 2)
        self.assertEqual(len(server.requests), 1)

    def test_broken_settings_warn_the_user_and_keep_a_copy(self):
        self.write_settings(b"[]")
        process = self.spawn()
        self.assertIn("foram corrigidas", self.wait_for(process, "AVISO"))
        self.assertEqual(process.wait(15), 0)
        self.assertEqual(len(list((self.root / "config").glob("settings.json.bak-*"))), 1)
