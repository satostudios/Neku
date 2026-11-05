import re, shutil, threading, time, zipfile
from pathlib import Path
from unittest import mock
from helpers import PROJECT, TempRootCase
from neko.config import Config
from neko.memory import Memory
from neko.skills import Skills, defender, files
from neko.skills.defender import ScanResult
from neko.skills.parser import Request, parse

CLEAN, THREAT, OFF = ScanResult("clean"), ScanResult("threat"), ScanResult("unavailable")

class SkillCase(TempRootCase):
    def setUp(self):
        super().setUp()
        self.home = self.root / "pessoal"
        self.folders = {key: self.home / key for key in files.KNOWN_FOLDERS}
        for path in self.folders.values():
            path.mkdir(parents=True)
        patches = [mock.patch.object(files, "known_folder", lambda key: self.folders[key]),
                   mock.patch.object(files, "user_folders", lambda: dict(self.folders))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.config = Config(self.root)
        self.memory = Memory(self.root)
        self.notices = []
        self.skills = Skills(self.root / "projeto", self.config, self.memory, self.notices.append)
        self.downloads = self.folders["downloads"]

    def say(self, text):
        request = parse(text)
        self.assertIsNotNone(request, text)
        return self.skills.handle(request)

    def file(self, folder, name, content="x"):
        path = self.folders[folder] / name
        path.write_text(content, encoding="utf-8")
        return path

    def archive(self, name="pacote.zip", members=None):
        path = self.downloads / name
        with zipfile.ZipFile(path, "w") as z:
            for member, content in (members or {"leia.txt": "oi"}).items():
                z.writestr(member, content)
        return path

class ArchiveSafetyTests(SkillCase):
    def extract(self, path):
        return files.safe_extract(path, self.downloads / "saida")

    def assert_refused(self, members):
        with self.assertRaises(files.UnsafeArchive):
            self.extract(self.archive(members=members))
        self.assertFalse((self.downloads / "saida").exists())

    def test_normal_archive(self):
        self.assertEqual(self.extract(self.archive(members={"a/b.txt": "1", "c.txt": "2"})), 2)
        self.assertEqual((self.downloads / "saida" / "a" / "b.txt").read_text(), "1")

    def test_path_traversal_is_refused(self):
        self.assert_refused({"../fora.txt": "x"})
        self.assertFalse((self.downloads / "fora.txt").exists())

    def test_deep_traversal_is_refused(self):
        self.assert_refused({"a/b/../../../../fora.txt": "x"})

    def test_absolute_path_is_refused(self):
        self.assert_refused({"/Windows/fora.txt": "x"})
        self.assert_refused({"C:/Windows/fora.txt": "x"})

    def test_alternate_data_stream_is_refused(self):
        self.assert_refused({"a.txt:oculto": "x"})

    def test_compression_bomb_is_refused(self):
        path = self.downloads / "bomba.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("zeros.bin", b"\0" * (200 * 1024 * 1024))
        with self.assertRaisesRegex(files.UnsafeArchive, "bomba"):
            self.extract(path)

    def test_too_many_files_is_refused(self):
        with mock.patch.object(files, "MAX_FILES", 2):
            self.assert_refused({"1": "x", "2": "x", "3": "x"})

    def test_password_protected_is_refused(self):
        path = self.archive()
        data = bytearray(path.read_bytes())
        for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            data[data.index(signature) + offset] |= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(files.UnsafeArchive, "senha"):
            self.extract(path)

    def test_corrupted_archive_is_refused(self):
        path = self.downloads / "ruim.zip"
        path.write_bytes(b"isto nao e um zip")
        with self.assertRaisesRegex(files.UnsafeArchive, "corrompido"):
            self.extract(path)

    def test_internet_mark_is_copied_to_extracted_files(self):
        path = self.archive()
        with open(f"{path}:Zone.Identifier", "w") as stream:
            stream.write("[ZoneTransfer]\nZoneId=3\n")
        self.extract(path)
        with open(f"{self.downloads / 'saida' / 'leia.txt'}:Zone.Identifier") as stream:
            self.assertIn("ZoneId=3", stream.read())

class InspectTests(SkillCase):
    def test_ordinary_files(self):
        self.file("documents", "nota.txt")
        self.assertEqual(files.inspect(self.folders["documents"])["risky"], [])

    def test_programs_are_flagged(self):
        self.file("documents", "instalar.exe")
        self.assertEqual(files.inspect(self.folders["documents"])["risky"], ["instalar.exe"])

    def test_disguised_file_is_flagged(self):
        self.file("documents", "foto.jpg.exe")
        self.assertEqual(files.inspect(self.folders["documents"])["disguised"], ["foto.jpg.exe"])

class ZipFlowTests(SkillCase):
    def run_zip(self, *results, members=None):
        path = self.archive(members=members)
        with mock.patch.object(defender, "scan", side_effect=list(results)) as scan:
            reply = self.skills.process_zip(path)
        return reply, scan

    def test_checks_before_and_after(self):
        reply, scan = self.run_zip(CLEAN, CLEAN)
        self.assertEqual(scan.call_count, 2)
        self.assertTrue((self.downloads / "pacote" / "leia.txt").exists())
        self.assertIn("Parece tranquilo", reply.text)

    def test_threat_stops_before_extracting(self):
        reply, _ = self.run_zip(THREAT)
        self.assertFalse((self.downloads / "pacote").exists())
        self.assertIn("Não abra", reply.text)
        self.assertIsNone(reply.confirm)

    def test_threat_inside_offers_no_way_to_open(self):
        reply, _ = self.run_zip(CLEAN, THREAT)
        self.assertIsNone(reply.confirm)
        self.assertIn("Não abra", reply.text)

    def test_without_antivirus_nothing_is_extracted(self):
        reply, _ = self.run_zip(OFF)
        self.assertFalse((self.downloads / "pacote").exists())
        self.assertIn("Não extraí", reply.text)

    def test_programs_inside_are_mentioned(self):
        reply, _ = self.run_zip(CLEAN, CLEAN, members={"setup.exe": "x"})
        self.assertIn("setup.exe", reply.text)
        self.assertIn("Abra só se confiar", reply.text)

    def test_disguised_file_gets_a_warning(self):
        reply, _ = self.run_zip(CLEAN, CLEAN, members={"foto.jpg.exe": "x"})
        self.assertIn("disfarçado", reply.text)

    def test_nothing_is_opened_without_asking(self):
        with mock.patch("os.startfile", create=True) as opened:
            reply, _ = self.run_zip(CLEAN, CLEAN)
            opened.assert_not_called()
            reply.confirm.on_yes()
            opened.assert_called_once()

    def test_existing_folder_is_not_overwritten(self):
        (self.downloads / "pacote").mkdir()
        self.run_zip(CLEAN, CLEAN)
        self.assertTrue((self.downloads / "pacote (1)" / "leia.txt").exists())

    def test_request_by_conversation_asks_first(self):
        self.archive()
        reply = self.say("descompacta o último zip")
        self.assertIsNotNone(reply.confirm)
        self.assertFalse((self.downloads / "pacote").exists())

class PermissionTests(SkillCase):
    def apps(self):
        return mock.patch.object(files, "start_apps", return_value=[{"Name": "Bloco de Notas", "AppID": "app.notas"}])

    def test_blocked_capability_does_nothing(self):
        self.config.data["permissions"]["open_apps"] = "deny"
        with self.apps(), mock.patch("subprocess.Popen") as started:
            reply = self.say("abre o bloco de notas")
        self.assertIn("bloqueada", reply.text)
        started.assert_not_called()

    def test_ask_runs_only_after_yes(self):
        with self.apps(), mock.patch("subprocess.Popen") as started:
            reply = self.say("abre o bloco de notas")
            started.assert_not_called()
            reply.confirm.on_yes()
            started.assert_called_once()

    def test_allow_runs_directly(self):
        self.config.data["permissions"]["open_apps"] = "allow"
        with self.apps(), mock.patch("subprocess.Popen") as started:
            self.say("abre o bloco de notas")
        self.assertEqual(started.call_args[0][0], ["explorer.exe", "shell:AppsFolder\\app.notas"])

    def test_only_listed_apps_open(self):
        with self.apps(), mock.patch("subprocess.Popen") as started:
            reply = self.say("abre o programa malicioso.exe")
        self.assertIn("Não achei", reply.text)
        started.assert_not_called()

    def test_writing_always_asks_even_if_config_says_allow(self):
        self.config.data["permissions"]["write_files"] = "allow"
        reply = self.say("cria uma pasta Teste nos documentos")
        self.assertIsNotNone(reply.confirm)
        self.assertFalse((self.folders["documents"] / "Teste").exists())

    def test_web_search_is_encoded(self):
        self.config.data["permissions"]["open_web"] = "allow"
        with mock.patch("webbrowser.open") as opened:
            self.say("pesquisa café & leite?x=1")
        self.assertEqual(opened.call_args[0][0], "https://www.google.com/search?q=caf%C3%A9+%26+leite%3Fx%3D1")

    def test_search_reads_names_only_after_permission(self):
        self.file("documents", "relatorio final.pdf")
        reply = self.say("acha o arquivo relatorio")
        self.assertIn("relatorio final.pdf", reply.confirm.on_yes().text)

class FileActionTests(SkillCase):
    def test_create_folder(self):
        self.say("cria uma pasta Teste nos documentos").confirm.on_yes()
        self.assertTrue((self.folders["documents"] / "Teste").is_dir())

    def test_invalid_name_is_refused(self):
        for name in ("a/b", "..\\fora", "CON", "ni*ce"):
            self.assertIsNone(files.valid_name(name), name)

    def test_note_gets_txt_and_content(self):
        self.say("cria um arquivo lista com pão e leite").confirm.on_yes()
        self.assertEqual((self.folders["documents"] / "lista.txt").read_text(encoding="utf-8"), "pão e leite")

    def test_rename_keeps_extension(self):
        path = self.file("documents", "antigo.pdf")
        self.say("renomeia antigo.pdf para novo").confirm.on_yes()
        self.assertFalse(path.exists())
        self.assertTrue((self.folders["documents"] / "novo.pdf").exists())

    def test_move_never_overwrites(self):
        moved = self.file("documents", "nota.txt", "origem")
        self.file("pictures", "nota.txt", "destino")
        with mock.patch.object(self.skills, "_resolve", return_value=(moved, None)):
            self.skills.handle(Request("move", {"source": "x", "folder": "pictures"})).confirm.on_yes()
        self.assertEqual((self.folders["pictures"] / "nota.txt").read_text(encoding="utf-8"), "destino")
        self.assertEqual((self.folders["pictures"] / "nota (1).txt").read_text(encoding="utf-8"), "origem")

    def test_copy_keeps_the_original(self):
        path = self.file("documents", "foto.png")
        self.say("copia foto.png para imagens").confirm.on_yes()
        self.assertTrue(path.exists())
        self.assertTrue((self.folders["pictures"] / "foto.png").exists())

    def test_delete_always_goes_to_the_trash(self):
        path = self.file("documents", "velho.txt")
        with mock.patch.object(files, "send_to_trash") as trash:
            reply = self.say("apaga o arquivo velho.txt")
            trash.assert_not_called()
            reply.confirm.on_yes()
        trash.assert_called_once_with(path)

    def test_files_outside_personal_folders_are_refused(self):
        outside = self.root / "sistema.dll"
        outside.write_text("x")
        with mock.patch.object(self.skills, "_resolve", return_value=(outside, None)):
            for request in (Request("trash", {"target": "x"}), Request("move", {"source": "x", "folder": "documents"}),
                            Request("rename", {"source": "x", "name": "y"})):
                self.assertIn("pastas pessoais", self.skills.handle(request).text)

    def test_neko_never_touches_its_own_folder(self):
        project = self.folders["downloads"] / "NekoAI"
        project.mkdir()
        inside = project / "settings.json"
        inside.write_text("{}")
        skills = Skills(project, self.config, self.memory)
        with mock.patch.object(skills, "_resolve", return_value=(inside, None)):
            self.assertIn("pastas pessoais", skills.handle(Request("trash", {"target": "x"})).text)

    def test_ambiguous_name_asks_which_one(self):
        self.file("documents", "contrato a.pdf")
        self.file("documents", "contrato b.pdf")
        self.assertIn("mais de um", self.skills.handle(Request("trash", {"target": "contrato"})).text)

    def test_this_refers_to_the_last_file(self):
        path = self.file("documents", "nota.txt")
        self.skills.last_path = path
        self.assertEqual(self.skills._resolve("isso")[0], path)

class OrganizeTests(SkillCase):
    def old_file(self, name):
        path = self.downloads / name
        path.write_text("x")
        old = time.time() - 3600
        import os
        os.utime(path, (old, old))
        return path

    def test_preview_then_move_then_undo(self):
        self.old_file("foto.png")
        document = self.old_file("nota.pdf")
        reply = self.say("organiza meus downloads")
        self.assertIn("Imagens: 1", reply.text)
        self.assertTrue(document.exists())
        reply.confirm.on_yes()
        self.assertTrue((self.downloads / "Documentos" / "nota.pdf").exists())
        self.say("desfaz a organização")
        self.assertTrue(document.exists())

    def test_files_still_downloading_are_left_alone(self):
        (self.downloads / "filme.mp4.crdownload").write_text("x")
        (self.downloads / "novo.png").write_text("x")
        self.assertIn("já estão organizados", self.say("organiza meus downloads").text)

    def test_undo_without_history(self):
        self.assertIn("nenhuma organização", self.say("desfaz a organização").text)

class SystemTests(SkillCase):
    def test_system_summary(self):
        text = self.say("como está o pc?").text
        self.assertIn("Memória:", text)
        self.assertIn("Disco:", text)

    def test_help_lists_abilities(self):
        self.assertIn("Lixeira", self.say("o que você sabe fazer?").text)

    def test_timer_notifies(self):
        self.skills.handle(Request("timer", {"seconds": 0, "text": "tirar o bolo"}))
        limit = time.monotonic() + 2
        while not self.notices and time.monotonic() < limit:
            time.sleep(0.01)
        self.assertIn("tirar o bolo", self.notices[0].text)

    def test_failure_of_the_system_is_reported(self):
        with mock.patch.object(self.skills, "_system", side_effect=PermissionError()):
            self.assertIn("Não consegui", self.skills.handle(Request("system", {"topic": "x"})).text)

class SafetyByDesignTests(TempRootCase):
    def test_source_has_no_free_command_execution(self):
        for path in (PROJECT / "src").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"shell\s*=\s*True", path.name)
            self.assertNotRegex(text, r"\bos\.system\(|(?<![.\w])eval\(|(?<![.\w])exec\(|os\.popen", path.name)

    def test_no_permanent_deletion_in_the_skills(self):
        for path in (PROJECT / "src" / "neko" / "skills").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            allowed = {"manifests[-1].unlink()", "shutil.rmtree(destination, ignore_errors=True)"}
            found = set(re.findall(r"[\w\[\]\-.]*(?:\.unlink\(\)|rmtree\([^)]*\)|os\.remove\([^)]*\))", text))
            self.assertLessEqual(found, allowed, path.name)
