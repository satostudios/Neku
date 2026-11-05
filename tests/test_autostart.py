import os, sys
from unittest import mock
from helpers import TempRootCase
from neko import autostart

class FakeWinreg:
    """Registro em memória: os testes nunca tocam no registro real."""
    HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ = 1, 2, 1

    def __init__(self):
        self.values = {}

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def OpenKey(self, *args):
        return self.Key()

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

class AutostartTests(TempRootCase):
    def setUp(self):
        super().setUp()
        self.registry = FakeWinreg()
        patches = [mock.patch.dict(sys.modules, {"winreg":self.registry}),
                   mock.patch.dict(os.environ, {"APPDATA":str(self.root / "appdata")})]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        (self.root / ".venv" / "Scripts").mkdir(parents=True)
        (self.root / ".venv" / "Scripts" / "pythonw.exe").write_bytes(b"")

    def test_enable_registers_quoted_unicode_command(self):
        autostart.sync(self.root, True)
        command = self.registry.values[autostart.VALUE_NAME]
        self.assertEqual(command, f'"{self.root}\\.venv\\Scripts\\pythonw.exe" "{self.root}\\src\\main.py"')
        self.assertIn("ação", command)
        self.assertTrue(autostart.is_registered())

    def test_disable_removes_the_value(self):
        autostart.sync(self.root, True)
        autostart.sync(self.root, False)
        self.assertEqual(self.registry.values, {})
        self.assertFalse(autostart.is_registered())

    def test_disable_without_value_is_harmless(self):
        autostart.sync(self.root, False)

    def test_sync_rewrites_the_path_when_the_folder_moves(self):
        self.registry.values[autostart.VALUE_NAME] = '"C:\\antigo\\pythonw.exe" "C:\\antigo\\main.py"'
        autostart.sync(self.root, True)
        self.assertIn(str(self.root), self.registry.values[autostart.VALUE_NAME])

    def test_legacy_bat_is_removed(self):
        legacy = autostart.legacy_file()
        legacy.parent.mkdir(parents=True)
        legacy.write_text("@echo off")
        autostart.sync(self.root, False)
        self.assertFalse(legacy.exists())
