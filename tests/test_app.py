import json, shutil, tempfile, time, unittest
from pathlib import Path
from unittest import mock
from helpers import PROJECT, TempRootCase
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import neko.app as neko_app
from neko.app import ENGINE_DEFAULTS, NekoApp
from neko.reply import Reply
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore

qt = QApplication.instance() or QApplication([])
qt.setQuitOnLastWindowClosed(False)

class NekoCase(TempRootCase):
    def make(self, **settings):
        config = self.root / "config"
        config.mkdir(exist_ok=True)
        (config / "settings.json").write_text(json.dumps({"agent_onboarded": True, **settings}), encoding="utf-8")
        shutil.copytree(PROJECT / "pets", self.root / "pets", dirs_exist_ok=True)
        paths = Paths(root=self.root, dados=self.root / "data" / "cerebro")
        store = SettingsStore(paths)
        store.update(ENGINE_DEFAULTS)
        with mock.patch.object(neko_app, "GlobalHotkey"):
            neko = NekoApp(store, paths, self.root)
        neko.tray.icon.hide()
        self.addCleanup(self.shut, neko)
        return neko

    @staticmethod
    def shut(neko):
        for timer in neko.findChildren(QTimer):
            timer.stop()
        if neko.vision:
            neko.vision.stop()
        for widget in (neko.pet, neko.ball, neko.chat.bubble):
            widget.close()
        neko.runtime.stop()

class BodyTests(NekoCase):
    def test_small_body_with_the_sprite(self):
        neko = self.make()
        self.assertIs(neko.pet.pintor, neko.sprite)
        self.assertEqual((neko.pet.body.half_w * 2, neko.pet.body.half_h * 2), (48, 52))

    def test_stands_on_the_taskbar(self):
        neko = self.make()
        bottom = neko.bounds()[3]
        for _ in range(240):
            neko.pet.body.step(0.016, neko.bounds(), [], neko.screen_bounds(), neko.screen_geometries())
        self.assertTrue(neko.pet.body.grounded)
        self.assertEqual(neko.pet.body.y + neko.pet.body.half_h, bottom)

    def test_does_not_climb_on_windows(self):
        neko = self.make()
        neko.scan_windows()
        self.assertEqual(neko.platforms, [])

    def test_falls_back_to_the_taskbar_after_being_thrown(self):
        neko = self.make()
        neko.pet.body.jump(0, -2000)
        for _ in range(500):
            neko.pet.body.step(0.016, neko.bounds(), [], neko.screen_bounds(), neko.screen_geometries())
        self.assertEqual(neko.pet.body.y + neko.pet.body.half_h, neko.bounds()[3])

    def test_fun_stuff_starts_off(self):
        neko = self.make()
        for key in ("travessuras", "bolinha", "protesto", "fogos", "pousar_janelas"):
            self.assertFalse(neko.perms[key], key)

    def test_protest_stays_quiet_when_off(self):
        neko = self.make()
        neko.protest.grievance = 0.9
        neko._ultimo_think = None
        neko.think()
        self.assertEqual(neko.protest.stage, 0)

    def test_notebook_stays_hidden_so_he_stays_on_the_bar(self):
        neko = self.make()
        self.assertTrue(neko.mesa.escondido)
        self.assertFalse(neko.mesa.sentado)

    def test_notebook_choice_is_remembered(self):
        neko = self.make()
        neko.menu_alternar_notebook()
        self.assertTrue(neko.settings_neko.get("notebook_visible"))
        self.assertFalse(neko.mesa.escondido)

    def test_waits_a_minute_before_the_first_offer(self):
        neko = self.make()
        self.assertGreater(neko.agent.next_offer, time.monotonic() + 50)

    def test_saved_position_is_used(self):
        neko = self.make(window_pos=[300, 0])
        self.assertEqual(neko.pet.body.x, 300)

class FollowTests(NekoCase):
    def test_walks_along_the_bar_while_typing(self):
        neko = self.make()
        neko._typed_at = time.monotonic()
        with mock.patch.object(neko_app, "cursor_pos", return_value=(600, 300)):
            neko.frame()
        self.assertEqual(neko.behavior.seguir_x, 670)

    def test_stays_near_the_edge_without_leaving_the_screen(self):
        neko = self.make()
        left, _, right, _ = neko.bounds()
        self.assertLessEqual(neko._follow_x(right - 5), right - 40)
        self.assertGreaterEqual(neko._follow_x(left), left + 40)

    def test_only_moves_sideways(self):
        neko = self.make()
        floor = neko.pet.body.y
        neko._typed_at = time.monotonic()
        with mock.patch.object(neko_app, "cursor_pos", return_value=(100, 10)):
            neko.frame()
        self.assertEqual(neko.pet.body.y, floor)

    def test_not_while_idle(self):
        neko = self.make()
        neko.frame()
        self.assertIsNone(neko.behavior.seguir_x)

    def test_option_turns_it_off(self):
        neko = self.make(follow_mouse=False)
        neko._typed_at = time.monotonic()
        neko.frame()
        self.assertIsNone(neko.behavior.seguir_x)

    def test_waits_while_the_chat_is_open(self):
        neko = self.make()
        neko._typed_at = time.monotonic()
        neko.chat.bubble.show()
        neko.frame()
        self.assertEqual(neko.behavior.seguir_x, neko.pet.body.x)

class BrainTests(NekoCase):
    def test_new_channels_reach_the_network(self):
        neko = self.make()
        neko.agent.screen_pulse, neko.agent.error_pulse = 1.0, 1.0
        self.assertEqual(neko.sinais_extras(), {"TELA": 1.0, "ERRO": 1.0})

    def test_error_excites_the_help_motor(self):
        neko = self.make()
        quiet = self._rate(neko, {})
        excited = self._rate(self.make(), {"ERRO": 1.0, "TELA": 1.0})
        self.assertGreater(excited, quiet)

    @staticmethod
    def _rate(neko, channels):
        for _ in range(40):
            neko.brain.stimulate(channels)
            neko.brain.step(100)
        return neko.brain.motor_activity()["AJUDAR"]

    def test_user_feedback_teaches_the_network(self):
        neko = self.make()
        neko.agent.reward = 1.0
        with mock.patch.object(neko.brain, "learn") as learn:
            neko._ultimo_think = None
            neko.think()
        self.assertEqual(learn.call_args[0][0], 1.0)
        self.assertEqual(neko.agent.reward, 0.0)

    def test_neural_monitor_opens_with_the_new_motor(self):
        neko = self.make()
        neko.floats.open("neural")

class VisionWiringTests(NekoCase):
    def test_off_until_consent(self):
        neko = self.make()
        self.assertIsNone(neko.vision)
        self.assertEqual(neko.sprite.visao, "desligada")

    def test_led_shows_when_it_is_looking(self):
        neko = self.make(vision={"enabled": True})
        self.assertEqual(neko.sprite.visao, "ligada")
        neko.toggle_vision_pause()
        self.assertEqual(neko.sprite.visao, "pausada")

    def test_panic_turns_the_model_off(self):
        neko = self.make()
        with mock.patch.object(neko.tray.icon, "showMessage"), mock.patch.object(neko.runtime, "stop") as stop:
            neko.panic()
        stop.assert_called_once()

    def test_panic_stops_the_eyes(self):
        neko = self.make(vision={"enabled": True})
        neko.idle_seconds, neko.activity = 0, "IDLE"
        neko.sleep.asleep = False
        self.assertFalse(neko._vision_should_pause())
        with mock.patch.object(neko.tray.icon, "showMessage"):
            neko.panic()
        self.assertTrue(neko._vision_should_pause())
        self.assertEqual(neko.sprite.visao, "pausada")

    def test_pauses_when_the_body_is_hidden(self):
        neko = self.make(vision={"enabled": True})
        neko.idle_seconds = 0
        self.assertFalse(neko._vision_should_pause())
        neko.hidden = True
        self.assertTrue(neko._vision_should_pause())

    def test_does_not_look_when_you_are_away(self):
        neko = self.make(vision={"enabled": True})
        neko.idle_seconds = 500
        self.assertTrue(neko._vision_should_pause())

    def test_does_not_look_during_games(self):
        neko = self.make(vision={"enabled": True})
        neko.idle_seconds = 0
        neko.activity = "GAMING"
        self.assertTrue(neko._vision_should_pause())

    def test_consent_turns_on_eyes_and_downloads(self):
        neko = self.make(agent_onboarded=False)
        with mock.patch.object(neko.chat, "notice_ready") as signal:
            neko._welcome()
        reply = signal.emit.call_args[0][0]
        self.assertIn("ler o texto", reply.text)
        reply.confirm.on_yes()
        self.assertTrue(neko.settings_neko.get("vision")["enabled"])
        self.assertTrue(neko.settings_neko.get("watch_downloads"))

    def test_refusing_leaves_everything_off(self):
        neko = self.make(agent_onboarded=False)
        with mock.patch.object(neko.chat, "notice_ready") as signal:
            neko._welcome()
        signal.emit.call_args[0][0].confirm.on_no()
        self.assertFalse(neko.settings_neko.get("vision")["enabled"])
        self.assertTrue(neko.settings_neko.get("agent_onboarded"))

    def test_mood_changes_the_face(self):
        neko = self.make()
        neko.presence.mood("happy", 5)
        later = time.monotonic() + 2
        self.assertEqual(neko.emotion.update(neko.brain.motor_activity(), 0.0, neko.prof, later), "feliz")

    def test_replies_map_to_known_emotions(self):
        from pestinha.config import EMOTIONS
        for emotion in neko_app.MOODS.values():
            self.assertIn(emotion, EMOTIONS)
