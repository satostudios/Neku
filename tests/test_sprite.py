import itertools, unittest
from unittest import mock
import helpers
from PySide6.QtWidgets import QApplication
from neko.character import Evolution, STAGES, reaction, start_reaction
from neko.sprite import ALTURA, CORPO, LARGURA, Sprite
from helpers import TempRootCase

app = QApplication.instance() or QApplication([])

class SpriteTests(unittest.TestCase):
    def test_is_small_enough_for_the_taskbar(self):
        self.assertLessEqual(CORPO[0], 60)
        self.assertLessEqual(CORPO[1], 60)

    def test_each_emotion_has_its_own_face(self):
        sprite = Sprite()
        names = ["observando", "feliz", "curioso", "bravo", "assustado", "dramatico", "dormindo", "triste"]
        images = {name: sprite.imagem(name) for name in names}
        for first, second in itertools.combinations(names, 2):
            if {first, second} != {"bravo", "triste"} or True:
                self.assertNotEqual(images[first], images[second], (first, second))

    def test_blink_closes_the_eyes(self):
        sprite = Sprite()
        self.assertNotEqual(sprite.imagem(blink=0.08), sprite.imagem(blink=1.0))

    def test_gaze_moves_the_eyes(self):
        sprite = Sprite()
        self.assertNotEqual(sprite.imagem(gaze=(1.0, 0.0)), sprite.imagem(gaze=(-1.0, 0.0)))

    def test_vision_indicator_is_visible(self):
        sprite = Sprite()
        off = sprite.imagem()
        sprite.visao = "ligada"
        on = sprite.imagem()
        sprite.visao = "pausada"
        paused = sprite.imagem()
        self.assertEqual(len({off.cacheKey(), on.cacheKey(), paused.cacheKey()}), 3)
        self.assertNotEqual(off, on)
        self.assertNotEqual(on, paused)

    def test_thinking_and_working_take_over_the_screen(self):
        sprite = Sprite()
        face = sprite.imagem()
        sprite.atividade = "pensando"
        self.assertNotEqual(sprite.imagem(), face)
        sprite.atividade = "trabalhando"
        self.assertNotEqual(sprite.imagem(), face)

    def test_legs_lift_while_walking(self):
        body = mock.Mock(grounded=True, vx=100.0)
        walking = Sprite(body)
        with mock.patch("neko.sprite.time.monotonic", return_value=0.11):
            moving = walking.imagem()
        self.assertNotEqual(moving, Sprite().imagem())

    def test_legs_stay_visible_on_a_dark_taskbar(self):
        image = Sprite().imagem()
        bottom = range(image.height() - 12, image.height())
        light = [(x, y) for y in bottom for x in range(image.width())
                 if image.pixelColor(x, y).alpha() and image.pixelColor(x, y).lightness() > 90]
        self.assertTrue(light)

    def test_larger_unit_scales_the_body(self):
        small, large = Sprite(unidade=2).imagem(), Sprite(unidade=3).imagem()
        self.assertGreater(large.width(), small.width())
        self.assertEqual(LARGURA * 2, CORPO[0])
        self.assertEqual(ALTURA * 2, CORPO[1])

class CharacterTests(TempRootCase):
    def test_reaction_grows_with_the_difficulty(self):
        self.assertEqual(reaction(1, True)[0], "happy")
        self.assertEqual(reaction(2, True), ("proud", "sparkle"))
        self.assertEqual(reaction(3, True), ("excited", "sparkle"))

    def test_failure_on_a_hard_task_is_sad(self):
        self.assertEqual(reaction(1, False)[0], "confused")
        self.assertEqual(reaction(3, False)[0], "sad")

    def test_hard_tasks_show_effort(self):
        self.assertEqual(start_reaction(3)[:2], ("working", "sweat"))
        self.assertEqual(start_reaction(1)[0], "thinking")

    def test_evolution_advances_and_persists(self):
        evolution = Evolution(self.root)
        self.assertEqual(evolution.name, "Filhote")
        self.assertIsNone(evolution.gain(10))
        self.assertEqual(evolution.gain(STAGES[1][0]), "Curioso")
        self.assertEqual(Evolution(self.root).stage, 2)

    def test_damaged_progress_starts_over(self):
        path = self.root / "data" / "progress.json"
        path.parent.mkdir()
        for content in ("{quebrado", "[]", '{"xp": "muito"}', '{"xp": -5}'):
            path.write_text(content, encoding="utf-8")
            self.assertEqual(Evolution(self.root).xp, 0)

    def test_final_stage_has_no_next_goal(self):
        evolution = Evolution(self.root)
        evolution.gain(STAGES[-1][0])
        self.assertEqual(evolution.stage, len(STAGES))
        self.assertIsNone(evolution.next_goal)
