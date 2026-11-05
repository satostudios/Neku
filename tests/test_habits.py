import zipfile
from datetime import datetime
from unittest import mock
from helpers import TempRootCase
from neko.config import Config
from neko.habits import EVENT_MANUAL, SUGGEST_AFTER, DownloadTracker, Habits
from neko.memory import Memory
from neko.observer import Observer, rounded_quarter
from neko.skills import Skills, files

class TrackerTests(TempRootCase):
    def setUp(self):
        super().setUp()
        self.folder = self.root / "downloads"
        self.folder.mkdir()
        (self.folder / "antigo.zip").write_bytes(b"x")
        self.tracker = DownloadTracker(self.folder)

    def test_old_files_are_not_news(self):
        self.assertEqual(self.tracker.scan(), ([], []))

    def test_file_counts_only_after_it_stops_growing(self):
        path = self.folder / "novo.zip"
        path.write_bytes(b"12")
        self.assertEqual(self.tracker.scan()[0], [])
        path.write_bytes(b"1234")
        self.assertEqual(self.tracker.scan()[0], [])
        self.assertEqual(self.tracker.scan()[0], [path])
        self.assertEqual(self.tracker.scan()[0], [])

    def test_downloads_in_progress_are_ignored(self):
        (self.folder / "filme.mp4.crdownload").write_bytes(b"x")
        (self.folder / "outro.part").write_bytes(b"x")
        self.tracker.scan()
        self.assertEqual(self.tracker.scan()[0], [])

    def test_empty_file_waits(self):
        (self.folder / "vazio.zip").write_bytes(b"")
        self.tracker.scan()
        self.assertEqual(self.tracker.scan()[0], [])

    def test_folder_named_after_a_zip_is_an_extraction(self):
        (self.folder / "antigo").mkdir()
        self.assertEqual(self.tracker.scan()[1], ["antigo"])

    def test_unrelated_folder_is_not_an_extraction(self):
        (self.folder / "fotos").mkdir()
        self.assertEqual(self.tracker.scan()[1], [])

    def test_missing_folder_does_not_break(self):
        DownloadTracker(self.root / "nao existe").scan()

class HabitTests(TempRootCase):
    def setUp(self):
        super().setUp()
        self.folder = self.root / "downloads"
        self.folder.mkdir()
        patch = mock.patch.object(files, "known_folder", lambda key: self.folder)
        patch.start()
        self.addCleanup(patch.stop)
        self.config = Config(self.root)
        self.config.data["watch_downloads"] = True
        self.memory = Memory(self.root)
        self.notices = []
        self.skills = Skills(self.root, self.config, self.memory, self.notices.append)
        self.habits = Habits(self.memory, self.config, self.skills, self.notices.append)
        self.habits.start()

    def download(self, name):
        with zipfile.ZipFile(self.folder / name, "w") as z:
            z.writestr("leia.txt", "oi")
        self.habits.check()
        return self.habits.check()

    def extract_by_hand(self, stem):
        (self.folder / stem).mkdir()
        self.habits.check()

    def teach(self, times=SUGGEST_AFTER):
        for number in range(times):
            self.download(f"pacote{number}.zip")
            self.extract_by_hand(f"pacote{number}")

    def test_only_the_extension_is_recorded(self):
        self.download("segredo do projeto.zip")
        rows = self.memory.events("download")
        self.assertEqual([row[2] for row in rows], [".zip"])

    def test_nothing_happens_when_turned_off(self):
        self.config.data["watch_downloads"] = False
        self.download("pacote.zip")
        self.assertEqual(self.memory.events("download"), [])

    def test_pause_also_stops_the_watch(self):
        self.config.data["observation_paused"] = True
        self.download("pacote.zip")
        self.assertEqual(self.memory.events("download"), [])

    def test_suggests_only_after_the_habit_repeats(self):
        self.teach(SUGGEST_AFTER - 1)
        self.assertEqual(self.notices, [])
        self.download("mais.zip")
        self.extract_by_hand("mais")
        self.assertEqual(len(self.notices), 1)
        self.assertIsNotNone(self.notices[0].confirm)

    def test_learning_does_not_turn_on_automation_alone(self):
        self.teach()
        self.assertIs(self.config.get("automations")["extract_zip"], False)
        self.assertEqual(self.download("novo.zip"), [])

    def test_accepting_turns_it_on_and_records_it(self):
        self.teach()
        self.notices[0].confirm.on_yes()
        self.assertIs(Config(self.root).get("automations")["extract_zip"], True)
        self.assertIn("descompacte", (self.memory.memory_dir / "preferences.md").read_text(encoding="utf-8"))
        self.assertEqual([path.name for path in self.download("novo.zip")], ["novo.zip"])

    def test_declining_is_never_asked_again(self):
        self.teach()
        self.notices[0].confirm.on_no()
        self.download("mais.zip")
        self.extract_by_hand("mais")
        self.assertEqual(len(self.notices), 1)

    def test_only_zips_are_handled(self):
        self.teach()
        self.notices[0].confirm.on_yes()
        (self.folder / "foto.png").write_bytes(b"x")
        self.habits.check()
        self.assertEqual(self.habits.check(), [])

    def test_nekos_own_extraction_is_not_a_habit(self):
        path = self.folder / "meu.zip"
        self.download("meu.zip")
        with mock.patch("neko.skills.defender.scan", return_value=mock.Mock(clean=True, threat=False)):
            self.habits.handle_zip(path)
        self.habits.check()
        self.assertEqual(self.memory.events(EVENT_MANUAL), [])

class ObserverTests(TempRootCase):
    def test_time_is_approximate(self):
        self.assertEqual(rounded_quarter(datetime(2026, 11, 5, 14, 52, 33)), datetime(2026, 11, 5, 14, 45))

    def test_ignored_apps_are_case_insensitive(self):
        config = Config(self.root)
        config.data["ignored_apps"] = ["Banco.EXE"]
        self.assertIn("banco.exe", Observer(Memory(self.root), config).ignored())

    def test_old_records_are_removed_at_start(self):
        config = Config(self.root)
        memory = Memory(self.root)
        memory.log("foreground_app", "velho.exe", "2020-01-01T10:00")
        Observer(memory, config)
        self.assertEqual(memory.events(), [])
