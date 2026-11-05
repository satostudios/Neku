import faulthandler, importlib.util, json, logging, subprocess, sys, threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest import mock
from helpers import PROJECT, TempRootCase
from neko import diagnostics

class LoggingCase(TempRootCase):
    def setUp(self):
        super().setUp()
        hook, thread_hook = sys.excepthook, threading.excepthook
        self.addCleanup(self.restore, hook, thread_hook)

    def restore(self, hook, thread_hook):
        sys.excepthook, threading.excepthook = hook, thread_hook
        faulthandler.disable()
        logging.shutdown()
        logging.basicConfig(handlers=[logging.NullHandler()], force=True)
        if diagnostics._crash_file:
            diagnostics._crash_file.close()
            diagnostics._crash_file = None
        diagnostics._log_path = None
        diagnostics._notified = False

class LogTests(LoggingCase):
    def test_log_is_rotating_and_limited(self):
        diagnostics.setup(self.root)
        self.assertIsInstance(logging.getLogger().handlers[0], RotatingFileHandler)
        limit = (diagnostics.LOG_BACKUPS + 1) * diagnostics.LOG_MAX_BYTES
        line = "x" * 200
        for _ in range(2 * limit // len(line)):
            logging.getLogger("neko.teste").info(line)
        logging.shutdown()
        files = list((self.root / "logs").glob("neko.log*"))
        self.assertEqual(len(files), diagnostics.LOG_BACKUPS + 1)
        self.assertLess(sum(f.stat().st_size for f in files), limit + 1024)

    def test_unhandled_error_is_logged_and_reported_once(self):
        diagnostics.setup(self.root)
        with mock.patch.object(diagnostics, "show_error") as shown:
            for _ in range(3):
                try:
                    raise RuntimeError("falha de teste")
                except RuntimeError:
                    sys.excepthook(*sys.exc_info())
        shown.assert_called_once()
        logging.shutdown()
        self.assertIn("falha de teste", (self.root / "logs" / "neko.log").read_text(encoding="utf-8"))

    def test_failure_at_startup_is_logged_and_exits_with_error(self):
        spec = importlib.util.spec_from_file_location("neko_main", PROJECT / "src" / "main.py")
        main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main)
        main.ROOT = self.root
        with mock.patch.object(diagnostics, "show_error") as shown, \
             mock.patch("neko.app.run", side_effect=RuntimeError("falhou ao abrir")), \
             mock.patch.object(sys, "argv", ["main.py"]):
            self.assertEqual(main.main(), 1)
        shown.assert_called_once()
        logging.shutdown()
        self.assertIn("falhou ao abrir", (self.root / "logs" / "neko.log").read_text(encoding="utf-8"))

class ReportTests(TempRootCase):
    def test_windows_11_is_named_correctly(self):
        version = mock.Mock(major=10, build=26300)
        with mock.patch.object(sys, "getwindowsversion", return_value=version, create=True), \
             mock.patch.object(sys, "platform", "win32"):
            self.assertEqual(diagnostics._system_name(), "Windows 11 (build 26300)")

    def test_report_hides_the_user_folder(self):
        executable = str(Path.home() / "neko" / "python.exe")
        with mock.patch.object(sys, "executable", executable):
            report = diagnostics.report(self.root)
        self.assertNotIn(str(Path.home()), report)
        self.assertIn("%USERPROFILE%\\neko\\python.exe", report)

    def test_report_lists_the_essentials(self):
        self.write_settings({"monitor_active_app": True})
        report = diagnostics.report(self.root)
        for text in ("Python: ", "PySide6-Essentials: ", "psutil: ", "numpy: ", "Observar nome do app ativo: ligado",
                     "Guardar mensagens no diário: desligado", "Ler a tela: desligado"):
            self.assertIn(text, report)

    def test_report_names_the_bundled_model(self):
        self.write_settings({"llm": {"enabled": False, "use_bundled": True, "endpoint": "http://127.0.0.1:8080/v1"}})
        (self.root / "runtime" / "llama").mkdir(parents=True)
        (self.root / "runtime" / "llama" / "llama-server.exe").write_bytes(b"")
        (self.root / "models").mkdir()
        (self.root / "models" / "pequeno.gguf").write_bytes(b"")
        report = diagnostics.report(self.root)
        self.assertIn("LLM local: modelo embutido pequeno", report)
        self.assertIn("Modelo local instalado: sim", report)

    def test_report_changes_nothing_on_disk(self):
        self.write_settings(b"{invalido")
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        report = diagnostics.report(self.root)
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob("*")), before)
        self.assertIn("ausente ou inválido", report)

    def test_external_endpoint_is_flagged_without_showing_the_address(self):
        self.write_settings({"llm": {"enabled": True, "endpoint": "https://usuario:senha@servidor.example/v1"}})
        report = diagnostics.report(self.root)
        self.assertIn("RECUSADO", report)
        self.assertNotIn("servidor.example", report)
        self.assertNotIn("senha", report)

    def test_command_line_option_runs_without_qt(self):
        code = ("import runpy, sys; sys.argv = ['main.py', '--diagnostics']\n"
                "sys.modules['PySide6'] = None\n"
                f"runpy.run_path({str(PROJECT / 'src' / 'main.py')!r}, run_name='__main__')")
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, encoding="utf-8",
                                env={**__import__("os").environ, "PYTHONIOENCODING":"utf-8", "PYTHONDONTWRITEBYTECODE":"1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("diagnóstico", result.stdout)
