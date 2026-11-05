import fnmatch, os, re, subprocess, sys, unittest
from helpers import PROJECT

class PackagingTests(unittest.TestCase):
    def test_requirements_have_exact_versions(self):
        lines = (PROJECT / "requirements.txt").read_text(encoding="utf-8").split()
        self.assertTrue(lines)
        for line in lines:
            self.assertRegex(line, r"^[A-Za-z0-9.-]+==(\d+!)?\d+(\.\d+)*$")

    def test_only_the_qt_modules_in_essentials_are_used(self):
        used = set()
        for path in (PROJECT / "src").rglob("*.py"):
            used |= set(re.findall(r"from PySide6\.(\w+)", path.read_text(encoding="utf-8")))
        self.assertEqual(used, {"QtCore", "QtGui", "QtWidgets"})

    def test_gitignore_has_real_lines_and_covers_personal_data(self):
        raw = (PROJECT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("\\n", raw)
        rules = raw.splitlines()
        for path in ("config/settings.json", "data/neko.sqlite3", "data/memory/user_profile.md", "data/diary/2026-01-01.md"):
            self.assertTrue(any(fnmatch.fnmatch(path, rule) for rule in rules), path)
        self.assertIn(".venv/", rules)

    def test_batch_files_are_ascii_with_crlf(self):
        for path in (PROJECT / "scripts").glob("*.bat"):
            raw = path.read_bytes()
            raw.decode("ascii")
            self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"), path.name)

    def test_powershell_scripts_have_bom_and_valid_syntax(self):
        check = ("$errors = $null; $tokens = $null; "
                 "[void][System.Management.Automation.Language.Parser]::ParseFile($env:NEKO_PS1, [ref]$tokens, [ref]$errors); "
                 "$errors.Count")
        for path in (PROJECT / "scripts").glob("*.ps1"):
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"), path.name)
            result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", check],
                                    capture_output=True, text=True, env={**os.environ, "NEKO_PS1":str(path)})
            self.assertEqual(result.stdout.strip(), "0", path.name)

    def test_model_downloads_are_pinned_by_hash(self):
        text = (PROJECT / "scripts" / "instalar_modelo.ps1").read_text(encoding="utf-8-sig")
        self.assertEqual(len(re.findall(r'Sha = "[0-9a-f]{64}"', text)), 2)
        self.assertIn('$LlamaBuild = "b', text)
        self.assertIn("Test-Sha $part $Sha", text)

    def test_gpl_license_and_origin_are_kept(self):
        self.assertIn("GNU GENERAL PUBLIC LICENSE", (PROJECT / "LICENSE").read_text(encoding="utf-8"))
        notice = (PROJECT / "NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("mille-okws/pestinha", notice)
        self.assertIn("984fb86", notice)

    def test_third_party_images_were_not_copied(self):
        self.assertEqual(list((PROJECT / "pets").rglob("*.webp")), [])
        self.assertEqual(list((PROJECT / "assets").rglob("*.png")), [])

    def test_generated_folders_are_ignored(self):
        rules = (PROJECT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for rule in ("runtime/", ".venv/", "data/*", "config/*", "logs/*", "models/*"):
            self.assertIn(rule, rules)

    def test_numpy_does_not_reserve_memory_per_core(self):
        code = ("import neko, os, psutil\n"
                "before = psutil.Process().memory_full_info().private\n"
                "import numpy\n"
                "print((psutil.Process().memory_full_info().private - before) / 1048576)")
        env = {**os.environ, "PYTHONPATH":str(PROJECT / "src"), "PYTHONDONTWRITEBYTECODE":"1"}
        env.pop("OPENBLAS_NUM_THREADS", None)
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
        self.assertLess(float(result.stdout.strip()), 60, result.stderr)
