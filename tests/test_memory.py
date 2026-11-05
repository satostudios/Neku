import gc, time
from datetime import date, timedelta
import psutil
from helpers import TempRootCase
from neko.memory import Memory, commands, context
from neko.memory.assistant import MemoryAssistant
from neko.memory.store import BACKUPS_PER_FILE, ChangedOnDisk, contradicts, format_line, parse_entries, similar

class MemoryCase(TempRootCase):
    def setUp(self):
        super().setUp()
        self.memory = Memory(self.root)
        self.prefs = self.memory.memory_dir / "preferences.md"

class FileTests(MemoryCase):
    def test_creates_templates_in_path_with_accent(self):
        self.assertIn("Sou Neku", (self.memory.memory_dir / "identity.md").read_text(encoding="utf-8"))
        self.assertTrue((self.memory.memory_dir / "projects.md").exists())
        self.assertTrue((self.memory.memory_dir / "temporary.md").exists())

    def test_existing_memory_is_never_overwritten(self):
        self.prefs.write_text("minha edição manual", encoding="utf-8")
        Memory(self.root)
        self.assertEqual(self.prefs.read_text(encoding="utf-8"), "minha edição manual")

    def test_saved_line_has_origin_and_date(self):
        self.memory.add("preferences.md", "  gosto   de café ")
        self.assertIn(f"- gosto de café (conversa, {date.today().isoformat()})", self.prefs.read_text(encoding="utf-8"))

    def test_template_prose_is_not_a_memory(self):
        self.assertEqual(self.memory.personal_entries(), [])

    def test_manual_line_counts_as_memory(self):
        with self.prefs.open("a", encoding="utf-8") as f:
            f.write("Escrevi isto à mão\n- e isto também\n")
        texts = {entry.text: entry.origin for entry in self.memory.personal_entries()}
        self.assertEqual(texts, {"Escrevi isto à mão": "manual", "e isto também": "manual"})

    def test_rest_of_the_file_is_preserved_byte_by_byte(self):
        raw = "﻿# Minha lista\r\n\r\nNota solta   com espaços\r\n- primeiro\r\n- segundo\r\n<!-- comentário -->\r\n".encode("utf-8")
        self.prefs.write_bytes(raw)
        entry = next(e for e in self.memory.personal_entries() if e.text == "primeiro")
        self.memory.remove(entry)
        self.assertEqual(self.prefs.read_bytes(), raw.replace("- primeiro\r\n".encode(), b""))

    def test_append_keeps_crlf_and_bom(self):
        self.prefs.write_bytes("﻿# Lista\r\n- um".encode("utf-8"))
        self.memory.add("preferences.md", "dois")
        raw = self.prefs.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\r", raw)
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertIn(b"- um\r\n- dois", raw)

    def test_ansi_file_is_read_and_converted_with_backup(self):
        self.prefs.write_bytes("- gosto de açaí\n".encode("cp1252"))
        self.assertEqual(self.memory.personal_entries()[0].text, "gosto de açaí")
        self.memory.add("preferences.md", "e de café")
        text = self.prefs.read_bytes().decode("utf-8")
        self.assertIn("gosto de açaí", text)
        self.assertEqual(len(list((self.memory.memory_dir / ".backup").glob("preferences.*"))), 1)

    def test_change_makes_a_backup_that_restores_the_original(self):
        self.memory.add("preferences.md", "gosto de chá")
        original = self.prefs.read_bytes()
        self.memory.remove(self.memory.personal_entries()[0])
        backup = next((self.memory.memory_dir / ".backup").glob("preferences.*"))
        self.assertEqual(backup.read_bytes(), original)

    def test_old_backups_are_limited(self):
        self.memory.add("preferences.md", "gosto de chá")
        for number in range(BACKUPS_PER_FILE + 5):
            self.memory.replace(self.memory.personal_entries()[0], f"gosto de chá {number}")
        self.assertEqual(len(list((self.memory.memory_dir / ".backup").glob("preferences.*"))), BACKUPS_PER_FILE)

    def test_line_changed_by_hand_is_not_touched(self):
        self.memory.add("preferences.md", "gosto de chá")
        entry = self.memory.personal_entries()[0]
        text = self.prefs.read_text(encoding="utf-8")
        self.prefs.write_text(text.replace("chá", "mate"), encoding="utf-8")
        with self.assertRaises(ChangedOnDisk):
            self.memory.files.remove(entry)
        self.assertIn("mate", self.prefs.read_text(encoding="utf-8"))

    def test_editor_save_detects_external_change(self):
        text, stamp = self.memory.read_file("preferences.md")
        self.prefs.write_text(text + "- mudou por fora\n", encoding="utf-8")
        with self.assertRaises(ChangedOnDisk):
            self.memory.save_file("preferences.md", text + "- do editor\n", stamp - 1)
        self.assertIn("mudou por fora", self.prefs.read_text(encoding="utf-8"))

    def test_editor_save_makes_a_backup(self):
        text, stamp = self.memory.read_file("preferences.md")
        self.memory.save_file("preferences.md", text + "- novo\n", stamp)
        self.assertEqual(len(list((self.memory.memory_dir / ".backup").glob("preferences.*"))), 1)

    def test_unknown_file_is_refused(self):
        with self.assertRaises(ValueError):
            self.memory.read_file("../../config/settings.json")

    def test_connections_are_closed(self):
        process = psutil.Process()
        gc.collect()
        gc.disable()
        self.addCleanup(gc.enable)
        before = process.num_handles()
        for _ in range(100):
            self.memory.log("x", "y")
        self.assertLess(process.num_handles() - before, 10)
        self.assertFalse(self.memory.db_path.with_name("neko.sqlite3-wal").exists())

    def test_events_can_be_exported_and_erased(self):
        self.memory.log("download", ".zip")
        path = self.root / "registros.json"
        self.assertEqual(self.memory.export_events(path), 1)
        self.assertIn(".zip", path.read_text(encoding="utf-8"))
        self.memory.clear_events()
        self.assertEqual(self.memory.events(), [])

    def test_old_events_are_purged(self):
        self.memory.log("x", "antigo", (date.today() - timedelta(days=90)).isoformat())
        self.memory.log("x", "novo")
        self.memory.purge_events(30)
        self.assertEqual([row[2] for row in self.memory.events()], ["novo"])

class KnowledgeTests(MemoryCase):
    def test_similar_text_is_a_duplicate(self):
        self.assertEqual(self.memory.add("preferences.md", "Gosto de café sem açúcar").status, "saved")
        self.assertEqual(self.memory.add("preferences.md", "gosto de cafe sem acucar").status, "duplicate")
        self.assertEqual(len(self.memory.personal_entries()), 1)

    def test_duplicate_is_detected_in_another_file(self):
        self.memory.add("important_memories.md", "A chave fica na gaveta")
        self.assertEqual(self.memory.add("preferences.md", "a chave fica na gaveta").status, "duplicate")

    def test_negation_is_a_contradiction(self):
        self.assertTrue(contradicts("Não gosto de café", "Gosto de café"))
        self.assertFalse(contradicts("Gosto de chá", "Gosto de café"))

    def test_changed_fact_is_a_contradiction(self):
        self.assertTrue(contradicts("Meu nome é Ana", "Meu nome é Silva"))
        self.assertTrue(contradicts("Moro em Olinda", "Moro em Recife"))
        self.assertFalse(contradicts("Meu nome é Ana", "Meu time é o Sport"))

    def test_contradiction_is_not_saved(self):
        self.memory.add("preferences.md", "Gosto de café")
        result = self.memory.add("preferences.md", "Não gosto de café")
        self.assertEqual(result.status, "conflict")
        self.assertEqual(len(self.memory.personal_entries()), 1)

    def test_different_things_are_not_similar(self):
        self.assertFalse(similar("Gosto de café", "Moro em Recife"))

    def test_expired_notes_stop_counting_but_stay_in_the_file(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        path = self.memory.memory_dir / "temporary.md"
        with path.open("a", encoding="utf-8") as f:
            f.write(format_line("Reunião antiga", until=yesterday) + "\n")
        self.assertEqual(self.memory.personal_entries(), [])
        self.assertIn("Reunião antiga", path.read_text(encoding="utf-8"))

    def test_legacy_format_is_understood(self):
        entry = parse_entries("preferences.md", "- gosto de chá (registrado em 2026-11-04)\n")[0]
        self.assertEqual((entry.text, entry.day, entry.origin), ("gosto de chá", "2026-11-04", "conversa"))

class ContextTests(MemoryCase):
    def fill(self, count):
        lines = "".join(format_line(f"memória número {i} sobre assuntos diversos") + "\n" for i in range(count))
        with self.prefs.open("a", encoding="utf-8") as f:
            f.write(lines)

    def test_budget_is_respected_without_cutting_entries(self):
        self.fill(300)
        text = self.memory.context_for("memória assuntos", 800)
        self.assertLessEqual(len(text), 800)
        self.assertIn("memória número", text)
        for line in text.splitlines():
            self.assertTrue(line.endswith(("diversos", "local.", "Curioso", "Prestativo", "Brincalhão")), line)

    def test_relevant_memory_comes_first(self):
        self.fill(300)
        self.memory.add("preferences.md", "Gosto de pizza de calabresa")
        self.assertIn("pizza", self.memory.context_for("qual pizza eu gosto?", 500))

    def test_identity_is_included_when_it_fits(self):
        self.fill(300)
        self.assertIn("Sou Neku", self.memory.context_for("nada", 300))

    def test_unrelated_memories_stay_out(self):
        self.fill(30)
        self.assertNotIn("memória número", self.memory.context_for("capital do Brasil"))

    def test_each_memory_shows_its_type(self):
        self.memory.add("preferences.md", "Gosto de chá")
        self.memory.add("temporary.md", "Dentista amanhã", until="2099-01-01")
        (self.memory.memory_dir / "learned_behaviors.md").write_text("- Parece gostar de música\n", encoding="utf-8")
        text = self.memory.context_for("chá dentista música")
        self.assertIn("[preferência", text)
        self.assertIn("[temporário", text)
        self.assertIn("vale até 2099-01-01", text)
        self.assertIn("[hipótese] Parece gostar de música", text)

    def test_search_with_2000_memories_is_fast(self):
        self.fill(2000)
        start = time.perf_counter()
        self.memory.context_for("o que eu gosto de fazer na segunda?")
        self.assertLess(time.perf_counter() - start, 0.2)

class AssistantTests(MemoryCase):
    def setUp(self):
        super().setUp()
        self.assistant = MemoryAssistant(self.memory)

    def say(self, text):
        return self.assistant.handle(commands.parse(text))

    def test_remember_cites_the_file(self):
        self.assertIn("preferences.md", self.say("lembre que eu gosto de café").text)
        self.assertEqual(len(self.memory.personal_entries()), 1)

    def test_passwords_are_refused(self):
        reply = self.say("lembre que minha senha é 1234")
        self.assertIn("Prefiro não guardar", reply.text)
        self.assertEqual(self.memory.personal_entries(), [])

    def test_passwords_are_refused_in_corrections(self):
        self.memory.add("preferences.md", "Gosto de chá")
        self.assertIn("Prefiro não guardar", self.say("corrija chá para senha 1234").text)

    def test_forget_needs_confirmation(self):
        self.say("lembre que eu gosto de café")
        reply = self.say("esquece o café")
        self.assertEqual(len(self.memory.personal_entries()), 1)
        self.assertIn("backup", reply.confirm.on_yes().text)
        self.assertEqual(self.memory.personal_entries(), [])

    def test_saying_no_changes_nothing(self):
        self.say("lembre que eu gosto de café")
        self.say("esquece o café").confirm.on_no()
        self.assertEqual(len(self.memory.personal_entries()), 1)

    def test_forget_what_does_not_exist(self):
        self.assertIn("Nada mudou", self.say("esquece o jazz").text)

    def test_forget_this_uses_the_last_saved(self):
        self.say("lembre que eu gosto de café")
        reply = self.say("esquece isso")
        reply.confirm.on_yes()
        self.assertEqual(self.memory.personal_entries(), [])

    def test_too_many_matches_ask_for_detail(self):
        for number in range(5):
            self.memory.add_unchecked("preferences.md", f"Café tipo {number}")
        reply = self.say("esquece o café")
        self.assertIsNone(reply.confirm)
        self.assertIn("mais específico", reply.text)

    def test_forget_all_never_deletes(self):
        self.say("lembre que eu gosto de café")
        reply = self.say("esqueça tudo")
        self.assertIsNone(reply.confirm)
        self.assertEqual(len(self.memory.personal_entries()), 1)

    def test_correct_replaces_after_confirmation(self):
        self.say("lembre que meu nome é Silva")
        reply = self.say("corrija: meu nome é Ana")
        self.assertEqual(self.memory.personal_entries()[0].text, "Meu nome é Silva")
        reply.confirm.on_yes()
        self.assertEqual(self.memory.personal_entries()[0].text, "Meu nome é Ana")

    def test_replace_shows_before_and_after(self):
        self.say("lembre que moro em Recife")
        reply = self.say("corrija Recife para Olinda")
        self.assertIn("Moro em Recife → Moro em Olinda", reply.text)
        reply.confirm.on_yes()
        self.assertEqual(self.memory.personal_entries()[0].text, "Moro em Olinda")

    def test_change_on_disk_during_confirmation_is_safe(self):
        self.say("lembre que eu gosto de café")
        reply = self.say("esquece o café")
        self.prefs.write_text("# nova versão\n", encoding="utf-8")
        self.assertIn("mudou", reply.confirm.on_yes().text)

    def test_query_lists_memories(self):
        self.say("lembre que eu gosto de café")
        self.assertIn("café", self.say("o que você sabe sobre café?").text)
        self.assertIn("café", self.say("o que você lembra sobre mim?").text)

    def test_query_without_results_is_honest(self):
        self.assertIn("Ainda não guardei", self.say("o que você sabe sobre física?").text)

    def test_reminder_without_time_is_honest(self):
        self.assertIn("não consigo avisar sozinho", self.say("me lembra de comprar pão").text)
