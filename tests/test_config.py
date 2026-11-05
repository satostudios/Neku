import json
from helpers import TempRootCase
from neko.config import Config, DEFAULTS

class ConfigTests(TempRootCase):
    def backups(self):
        return list((self.root / "config").glob("settings.json.bak-*"))

    def test_creates_safe_defaults(self):
        config = Config(self.root)
        self.assertFalse(config.get("start_with_windows"))
        self.assertFalse(config.get("monitor_active_app"))
        self.assertFalse(config.get("save_chat_history"))
        self.assertFalse(config.get("llm")["enabled"])
        self.assertTrue((self.root / "config" / "settings.json").exists())

    def test_broken_json_keeps_a_backup_and_opens_with_defaults(self):
        original = b'{"mascot_name":"Mimi",}'
        path = self.write_settings(original)
        config = Config(self.root)
        self.assertEqual(config.get("mascot_name"), "Neku")
        self.assertEqual(config.backup_path.read_bytes(), original)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["mascot_name"], "Neku")

    def test_utf8_bom_is_accepted(self):
        self.write_settings(b'\xef\xbb\xbf{"mascot_name":"Mimi","start_with_windows":true}')
        config = Config(self.root)
        self.assertEqual(config.get("mascot_name"), "Mimi")
        self.assertTrue(config.get("start_with_windows"))
        self.assertEqual(self.backups(), [])

    def test_root_that_is_not_an_object_recovers(self):
        for raw in (b"[]", b"null", b'"oi"', b"123"):
            with self.subTest(raw=raw):
                self.write_settings(raw)
                config = Config(self.root)
                self.assertEqual(config.get("mascot_name"), "Neku")
                self.assertEqual(config.backup_path.read_bytes(), raw)

    def test_invalid_value_is_replaced_and_the_rest_is_kept(self):
        self.write_settings({"mascot_name": "Mimi", "observation_interval_seconds": "abc",
                             "start_with_windows": 1, "llm": {"timeout_seconds": 0, "model": "meu"}})
        config = Config(self.root)
        self.assertEqual(config.get("mascot_name"), "Mimi")
        self.assertEqual(config.get("llm")["model"], "meu")
        self.assertEqual(config.get("observation_interval_seconds"), DEFAULTS["observation_interval_seconds"])
        self.assertIs(config.get("start_with_windows"), False)
        self.assertEqual(config.get("llm")["timeout_seconds"], DEFAULTS["llm"]["timeout_seconds"])
        self.assertEqual(len(self.backups()), 1)

    def test_section_with_wrong_type_is_restored(self):
        self.write_settings({"llm": "texto"})
        self.assertEqual(Config(self.root).get("llm"), DEFAULTS["llm"])

    def test_boolean_is_not_accepted_as_number(self):
        self.write_settings({"observation_interval_seconds": True})
        self.assertEqual(Config(self.root).get("observation_interval_seconds"), 30)

    def test_unknown_keys_survive(self):
        path = self.write_settings({"show_notifications": True})
        Config(self.root)
        self.assertIs(json.loads(path.read_text(encoding="utf-8"))["show_notifications"], True)

    def test_valid_file_is_not_rewritten_nor_copied(self):
        Config(self.root)
        path = self.root / "config" / "settings.json"
        before = path.stat().st_mtime_ns
        Config(self.root)
        self.assertEqual(path.stat().st_mtime_ns, before)
        self.assertEqual(self.backups(), [])

    def test_save_leaves_no_temporary_file(self):
        config = Config(self.root)
        config.set("mascot_name", "Mimi")
        self.assertEqual(Config(self.root).get("mascot_name"), "Mimi")
        self.assertEqual([p.name for p in (self.root / "config").iterdir()], ["settings.json"])
