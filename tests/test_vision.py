import re, unittest
from datetime import date, datetime, timedelta
from unittest import mock
import numpy as np
from helpers import PROJECT, TempRootCase
from neko.agent import capture, commands, insights, privacy
from neko.agent.journal import ScreenJournal, Snapshot
from neko.agent.vision import VisionWorker
from neko.config import Config

def snap(text="um texto qualquer na tela", app="word.exe", title="Documento", quando=None):
    return Snapshot(quando or datetime.now(), app, title, text)

class PrivacyTests(unittest.TestCase):
    def test_password_managers_and_system_prompts_are_private(self):
        for app in ("keepass.exe", "Bitwarden.exe", "consent.exe", "credentialuibroker.exe", "lockapp.exe"):
            self.assertTrue(privacy.is_private(app, "qualquer"), app)

    def test_private_titles(self):
        for title in ("Nova guia - Modo InPrivate", "Guia anônima", "Banco do Brasil - Conta", "Nubank", "Itaú", "Alterar senha",
                      "Login: password reset", "Incognito tab"):
            self.assertTrue(privacy.is_private("chrome.exe", title), title)

    def test_ordinary_windows_are_not_private(self):
        for title in ("Relatório - Word", "main.py - Antigravity", "YouTube", "Bancada de testes"):
            self.assertFalse(privacy.is_private("chrome.exe", title), title)

    def test_user_lists_are_respected(self):
        self.assertTrue(privacy.is_private("Steam.EXE", "x", ignored_apps=["steam.exe"]))
        self.assertTrue(privacy.is_private("word.exe", "Planilha de Salários", ignored_titles=["planilha de salarios"]))

    def test_sensitive_text_is_hidden(self):
        cases = {"CPF 123.456.789-09 aqui": "123.456.789-09", "cartão 4111 1111 1111 1111": "4111 1111 1111 1111",
                 "senha: abc123": "abc123", "password=hunter2": "hunter2", "CNPJ 12.345.678/0001-90": "12.345.678/0001-90",
                 "api_key: sk-abcdefghijklmnopqrstuvwx": "sk-abcdefghijklmnopqrstuvwx",
                 "token eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4": "eyJhbGciOiJIUzI1"}
        for text, secret in cases.items():
            self.assertNotIn(secret, privacy.redact(text), text)

    def test_ordinary_text_is_kept(self):
        text = "Reunião às 15h, sala 12. Total de R$ 1.500,00. Versão 2.4.1"
        self.assertEqual(privacy.redact(text), text)

class CaptureTests(unittest.TestCase):
    def frame(self):
        return capture.Frame(np.full((100, 200, 4), 200, dtype=np.uint8))

    def test_hidden_area_is_erased(self):
        frame = self.frame()
        frame.hide((10, 20, 50, 60))
        self.assertTrue((frame.pixels[20:60, 10:50] == 0).all())
        self.assertTrue((frame.pixels[70:, 60:] == 200).all())

    def test_coordinates_follow_the_virtual_screen(self):
        frame = capture.Frame(np.full((100, 200, 4), 200, dtype=np.uint8), left=-100, top=0)
        frame.hide((-100, 0, -50, 10))
        self.assertTrue((frame.pixels[0:10, 0:50] == 0).all())

    def test_same_image_is_not_a_change(self):
        signature = self.frame().signature()
        self.assertFalse(capture.changed(signature, signature))

    def test_different_image_is_a_change(self):
        frame = self.frame()
        before = frame.signature()
        frame.pixels[:] = 0
        self.assertTrue(capture.changed(before, frame.signature()))

    def test_first_look_counts_as_a_change(self):
        self.assertTrue(capture.changed(None, self.frame().signature()))

    def test_small_noise_is_ignored(self):
        frame = capture.Frame(np.full((1080, 1920, 4), 200, dtype=np.uint8))
        before = frame.signature()
        frame.pixels[0, 0] = 0
        self.assertFalse(capture.changed(before, frame.signature()))

class WorkerTests(TempRootCase):
    def worker(self, paused=False):
        self.seen = []
        self.config = Config(self.root)
        worker = VisionWorker(self.config, self.seen.append, lambda: paused)
        worker.reader = mock.Mock()
        worker.reader.read.return_value = "Texto visível na tela do usuário\nsenha: abc123"
        return worker

    def look(self, worker, active=("word.exe", "Documento", (0, 0, 50, 50)), windows=(), pixels=200):
        frame = capture.Frame(np.full((100, 200, 4), pixels, dtype=np.uint8))
        with mock.patch.object(capture, "foreground", return_value=active), mock.patch.object(capture, "grab", return_value=frame), \
             mock.patch.object(capture, "visible_windows", return_value=list(windows)):
            result = worker.look()
        return result, frame

    def test_reads_and_redacts_before_anything_else_sees_the_text(self):
        result, _ = self.look(self.worker())
        self.assertIn("Texto visível", result.texto)
        self.assertNotIn("abc123", result.texto)
        self.assertEqual(self.seen, [result])

    def test_unchanged_screen_skips_the_ocr(self):
        worker = self.worker()
        self.look(worker)
        self.look(worker)
        worker.reader.read.assert_called_once()

    def test_private_window_is_blanked_before_the_ocr(self):
        worker = self.worker()
        _, frame = self.look(worker, windows=[("keepass.exe", "Cofre", (10, 10, 60, 60))])
        self.assertTrue((frame.pixels[10:60, 10:60] == 0).all())

    def test_private_foreground_records_no_name(self):
        result, _ = self.look(self.worker(), active=("chrome.exe", "Nubank - Conta", (0, 0, 50, 50)))
        self.assertEqual(result.app, "privado")
        self.assertEqual(result.titulo, "")

    def test_neko_does_not_read_itself(self):
        worker = self.worker()
        worker.own_windows = lambda: [(0, 0, 40, 40)]
        _, frame = self.look(worker)
        self.assertTrue((frame.pixels[0:40, 0:40] == 0).all())

    def test_empty_screen_is_not_reported(self):
        worker = self.worker()
        worker.reader.read.return_value = "oi"
        self.assertIsNone(self.look(worker)[0])
        self.assertEqual(self.seen, [])

    def test_no_foreground_window_reads_nothing(self):
        worker = self.worker()
        with mock.patch.object(capture, "foreground", return_value=None), mock.patch.object(capture, "grab") as grab:
            self.assertIsNone(worker.look())
        grab.assert_not_called()

    def test_stop_ends_the_thread(self):
        worker = self.worker(paused=True)
        worker.config.data["vision"]["interval_seconds"] = 3
        worker.start()
        worker.stop()
        worker.join(2)
        self.assertFalse(worker.is_alive())

class JournalTests(TempRootCase):
    def journal(self, days=7):
        return ScreenJournal(self.root / "tela", days)

    def test_saves_text_and_finds_it(self):
        journal = self.journal()
        journal.add(snap("Proposta comercial para o cliente Acme"))
        found = journal.search("proposta acme")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["app"], "word.exe")

    def test_only_text_files_are_written(self):
        journal = self.journal()
        journal.add(snap())
        self.assertEqual({path.suffix for path in (self.root / "tela").iterdir()}, {".jsonl"})

    def test_nearly_identical_screens_are_not_repeated(self):
        journal = self.journal()
        base = " ".join(f"{letter}{other}assunto" for letter in "abcdefgh" for other in "ijklm")
        self.assertTrue(journal.add(snap(base)))
        self.assertFalse(journal.add(snap(base + " extra")))

    def test_new_content_is_saved(self):
        journal = self.journal()
        journal.add(snap("relatório financeiro do trimestre"))
        self.assertTrue(journal.add(snap("receita de bolo de cenoura")))

    def test_long_text_is_limited(self):
        journal = self.journal()
        journal.add(snap("x " * 9000))
        self.assertLessEqual(len(journal._read(date.today())[0]["texto"]), 4000)

    def test_finds_by_time(self):
        journal = self.journal()
        today = datetime.now().replace(hour=9, minute=0)
        journal.add(snap("manhã de trabalho no relatório", quando=today))
        journal.add(snap("tarde com outra atividade diferente", quando=today.replace(hour=15)))
        self.assertIn("tarde", journal.at(15, 10)["texto"])

    def test_old_days_are_erased(self):
        journal = self.journal(days=7)
        journal.add(snap("antigo demais", quando=datetime.now() - timedelta(days=30)))
        journal.add(snap("recente de hoje"))
        journal.purge()
        self.assertEqual(journal.days(), [date.today().isoformat()])

    def test_clear_erases_everything(self):
        journal = self.journal()
        journal.add(snap())
        journal.clear()
        self.assertEqual(journal.days(), [])
        self.assertEqual(journal.search("texto"), [])

    def test_damaged_lines_are_skipped(self):
        journal = self.journal()
        journal.add(snap("linha boa aqui"))
        with journal._path(date.today()).open("a", encoding="utf-8") as stream:
            stream.write("{quebrado\n[]\n")
        self.assertEqual(len(journal.search("linha")), 1)

class InsightTests(unittest.TestCase):
    def test_error_is_found(self):
        cases = ["Traceback (most recent call last):\n  File x\nValueError: valor inválido", "npm ERR! TypeError: x is not a function",
                 "Erro: arquivo não encontrado", "Build failed", "Acesso negado"]
        for text in cases:
            self.assertEqual(insights.detect(snap(text))[0].kind, "erro", text)

    def test_specific_error_line_is_preferred(self):
        text = "Traceback (most recent call last):\n  File a.py\nValueError: valor inválido"
        self.assertEqual(insights.find_error(text), "ValueError: valor inválido")

    def test_ordinary_text_has_no_error(self):
        for text in ("Reunião de equipe às 15h", "Terror é meu gênero favorito", "O erro é humano, dizia o texto"):
            self.assertEqual(insights.detect(snap(text)), [], text)

    def test_long_text_can_be_summarized(self):
        self.assertEqual(insights.detect(snap("palavra " * 300))[0].kind, "resumo")

class CommandTests(unittest.TestCase):
    def check(self, phrases, kind):
        for phrase in phrases:
            command = commands.parse(phrase)
            self.assertIsNotNone(command, phrase)
            self.assertEqual(command.kind, kind, phrase)

    def test_look(self):
        self.check(["o que você está vendo?", "o que tem na minha tela?", "lê a tela", "olha a tela", "neko, o que vc tá vendo?",
                    "descreve minha tela", "você consegue ver a tela?"], "look")

    def test_summary(self):
        self.check(["resume a tela", "resuma isso", "resume essa página", "pode resumir o texto?"], "summary")

    def test_find(self):
        self.assertEqual(commands.parse("procura orçamento na tela").query, "orçamento")

    def test_recall(self):
        self.assertEqual(commands.parse("onde eu vi aquele contrato?").query, "aquele contrato")
        self.assertEqual(commands.parse("o que eu vi sobre impostos?").query, "impostos")
        command = commands.parse("o que eu estava fazendo às 15h30?")
        self.assertEqual((command.hour, command.minute), (15, 30))

    def test_control(self):
        self.check(["para de olhar", "pausa a visão", "não olhe minha tela"], "pause")
        self.check(["volta a olhar", "retoma a visão"], "resume")
        self.check(["apaga o que você viu", "esquece tudo o que você leu"], "forget")

    def test_learning_question(self):
        self.check(["o que você aprendeu?", "sobre o que eu mais trabalho?"], "topics")

    def test_conversation_is_left_alone(self):
        for phrase in ("oi, tudo bem?", "minha tela quebrou", "abre a pasta downloads", "lembre que gosto de café",
                       "vi um filme ontem", "esqueci minha senha", "o que você sabe fazer?", "procura arquivos .pdf em documentos",
                       "resumo da ópera: deu certo", "resume o filme Titanic para mim"):
            self.assertIsNone(commands.parse(phrase), phrase)

    def test_invalid_hour_is_ignored(self):
        self.assertIsNone(commands.parse("o que eu estava fazendo às 45h?"))

    def test_questions_about_the_screen_are_recognized(self):
        self.assertTrue(commands.refers_to_screen("o que significa esse erro?"))
        self.assertFalse(commands.refers_to_screen("qual a capital do Brasil?"))

class SafetyTests(unittest.TestCase):
    def test_vision_code_cannot_act_on_the_computer(self):
        for name in ("vision.py", "ocr.py", "capture.py", "journal.py", "insights.py", "privacy.py"):
            text = (PROJECT / "src" / "neko" / "agent" / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"import skills|from \.\.skills|subprocess|webbrowser|startfile|urllib|socket", name)

    def test_vision_never_saves_images(self):
        for path in (PROJECT / "src" / "neko" / "agent").glob("*.py"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"\.save\(.*\.(png|jpg|bmp)|imwrite|tofile", path.name)
