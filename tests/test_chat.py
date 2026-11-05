import time
from unittest import mock
from helpers import TempRootCase
from PySide6.QtCore import QRect, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from neko.app import WELCOME
from neko.bubble import VIEW_HEIGHT, ChatBubble
from neko.chat import ERROR_ANSWER, ChatController
from neko.reply import Confirmation, Reply

app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)

class StubCompanion:
    def __init__(self, delay=0, error=None, tokens=(), reply=None):
        self.delay, self.error, self.tokens, self.reply = delay, error, tokens, reply
        self.received = []

    def respond(self, text, on_token=None, on_progress=None):
        self.received.append(text)
        for token in self.tokens:
            on_token(token)
        time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.reply or Reply("resposta")

class StubBody:
    def __init__(self):
        self.moods, self.activities = [], []

    def rect(self):
        return QRect(600, 700, 48, 52)

    def mood(self, name, seconds=3.5):
        self.moods.append(name)

    def activity(self, name):
        self.activities.append(name)

def wait_until(condition, seconds=5):
    limit = time.monotonic() + seconds
    while time.monotonic() < limit and not condition():
        app.processEvents()
        time.sleep(0.005)
    return condition()

class ChatCase(TempRootCase):
    def make(self, companion=None, evolution=None):
        self.body = StubBody()
        chat = ChatController(companion or StubCompanion(), self.body, evolution)
        self.addCleanup(chat.bubble.deleteLater)
        return chat

    def talk(self, chat, text="olá"):
        chat.submit(text)
        self.assertTrue(wait_until(lambda: not chat.busy and not chat.bubble.pending))
        return chat.bubble.transcript()

class ChatTests(ChatCase):
    def test_interface_keeps_running_while_waiting_for_the_answer(self):
        chat = self.make(StubCompanion(delay=0.8))
        beats = []
        heartbeat = QTimer()
        heartbeat.timeout.connect(lambda: beats.append(time.perf_counter()))
        heartbeat.start(20)
        self.assertIn("resposta", self.talk(chat))
        heartbeat.stop()
        self.assertLess(max(b - a for a, b in zip(beats, beats[1:])), 0.5)

    def test_thinking_shows_on_the_body_and_clears(self):
        chat = self.make()
        self.talk(chat)
        self.assertEqual(self.body.activities, ["pensando", None])

    def test_failure_while_answering_is_shown_and_the_face_recovers(self):
        chat = self.make(StubCompanion(error=RuntimeError("falha")))
        with self.assertLogs("neko.chat", level="ERROR"):
            self.assertIn(ERROR_ANSWER, self.talk(chat))
        self.assertFalse(chat.busy)
        self.assertEqual(self.body.moods[-1], "sad")

    def test_second_message_is_ignored_while_busy(self):
        companion = StubCompanion()
        chat = self.make(companion)
        chat.busy = True
        chat.submit("olá")
        self.assertEqual(companion.received, [])

    def test_tokens_appear_as_they_arrive(self):
        chat = self.make(StubCompanion(tokens=("res", "pos", "ta"), reply=Reply("resposta")))
        self.assertEqual(self.talk(chat).count("resposta"), 1)

    def test_final_text_replaces_a_different_stream(self):
        chat = self.make(StubCompanion(tokens=("algo diferente",), reply=Reply("texto final")))
        transcript = self.talk(chat)
        self.assertIn("texto final", transcript)
        self.assertNotIn("algo diferente", transcript)

    def test_confirmation_runs_only_after_yes(self):
        done = []
        chat = self.make(StubCompanion(reply=Reply("Achei", confirm=Confirmation("Posso?", lambda: done.append(1) or Reply("feito")))))
        self.talk(chat)
        self.assertTrue(chat.bubble.waiting_answer)
        self.assertEqual(done, [])
        chat.bubble.yes.click()
        self.assertTrue(wait_until(lambda: done and not chat.busy))

    def test_no_keeps_everything_as_it_was(self):
        done = []
        chat = self.make(StubCompanion(reply=Reply("Achei", confirm=Confirmation("Posso?", lambda: done.append(1) or Reply("feito")))))
        self.talk(chat)
        chat.bubble.no.click()
        self.assertEqual(done, [])
        self.assertIsNone(chat.pending_confirm)

    def test_message_cannot_be_sent_while_a_question_is_open(self):
        companion = StubCompanion(reply=Reply("oi", confirm=Confirmation("Posso?", lambda: Reply("ok"))))
        chat = self.make(companion)
        self.talk(chat)
        chat.submit("outra coisa")
        self.assertEqual(len(companion.received), 1)

    def test_notice_shows_without_a_request(self):
        chat = self.make()
        chat.show_notice(Reply("Percebi uma coisa", mood="curious"))
        self.assertTrue(wait_until(lambda: not chat.bubble.pending))
        self.assertIn("Percebi uma coisa", chat.bubble.transcript())
        self.assertEqual(self.body.moods[-1], "curious")

    def offer(self, chat):
        done = []
        chat.show_notice(Reply("Quer ajuda?", confirm=Confirmation("Posso?", lambda: done.append(1) or Reply("ok"))))
        return done

    def test_opening_the_chat_dismisses_an_offer(self):
        chat = self.make()
        done = self.offer(chat)
        chat.open()
        self.assertFalse(chat.bubble.waiting_answer)
        self.assertFalse(chat.bubble.input.isHidden())
        self.assertIsNone(chat.pending_confirm)
        self.assertEqual(done, [])

    def test_you_can_type_after_dismissing_an_offer(self):
        companion = StubCompanion()
        chat = self.make(companion)
        self.offer(chat)
        chat.open()
        self.talk(chat)
        self.assertEqual(companion.received, ["olá"])

    def test_expired_offer_frees_the_chat(self):
        chat = self.make()
        self.offer(chat)
        chat.expire_offer()
        self.assertFalse(chat.bubble.waiting_answer)
        self.assertTrue(chat.bubble.isHidden())

    def test_questions_about_your_own_request_are_not_dropped(self):
        chat = self.make(StubCompanion(reply=Reply("Achei", confirm=Confirmation("Apago?", lambda: Reply("ok")))))
        self.talk(chat)
        chat.open()
        chat.expire_offer()
        self.assertTrue(chat.bubble.waiting_answer)
        self.assertIsNotNone(chat.pending_confirm)

    def test_plain_notice_is_not_an_offer(self):
        chat = self.make()
        chat.show_notice(Reply("Aviso: hora do café"))
        self.assertFalse(chat.pending_is_offer)

    def test_answering_an_offer_clears_its_mark(self):
        chat = self.make()
        self.offer(chat)
        chat.bubble.no.click()
        self.assertFalse(chat.pending_is_offer)

    def test_evolution_is_announced(self):
        evolution = mock.Mock()
        evolution.gain.return_value = "Curioso"
        chat = self.make(StubCompanion(reply=Reply("feito", xp=10)), evolution)
        self.assertIn("agora sou Curioso", self.talk(chat))

class BubbleTests(TempRootCase):
    def make(self):
        bubble = ChatBubble()
        self.addCleanup(bubble.deleteLater)
        return bubble

    def asked(self, text):
        bubble = self.make()
        bubble.say(text)
        bubble.ask("Posso?", "Pode", "Agora não")
        bubble._flush()
        bubble._render()
        bubble.show()
        app.processEvents()
        return bubble

    def test_long_question_is_shown_whole_without_scrolling(self):
        bubble = self.asked(" ".join(["uma frase que precisa ser lida"] * 20))
        self.assertGreater(bubble.view.height(), VIEW_HEIGHT)
        self.assertEqual(bubble.view.verticalScrollBar().maximum(), 0)

    def test_the_authorization_is_visible_before_you_answer(self):
        bubble = self.asked(WELCOME)
        self.assertEqual(bubble.view.verticalScrollBar().maximum(), 0)
        self.assertIn("inclusive mensagens e documentos", WELCOME)
        self.assertIn("7 dias", WELCOME)

    def test_bubble_goes_back_to_its_size_after_the_answer(self):
        bubble = self.asked(WELCOME)
        bubble.no.click()
        self.assertEqual(bubble.view.height(), VIEW_HEIGHT)
        self.assertFalse(bubble.input.isHidden())

    def test_a_grown_bubble_stays_above_the_body(self):
        chat = ChatCase.make(self)
        chat.show_notice(Reply(WELCOME, confirm=Confirmation("Posso?", lambda: Reply("ok"))))
        bubble = chat.bubble
        self.assertLessEqual(bubble.y() + bubble.sizeHint().height(), self.body.rect().top() + 14)

    def test_html_from_the_model_is_never_rendered(self):
        bubble = self.make()
        bubble.say("<img src=x><b>oi</b>")
        bubble._flush()
        bubble._render()
        self.assertIn("&lt;img", bubble.view.toHtml())
        self.assertNotIn("<img", bubble.view.toHtml())

    def test_enter_sends_and_clears(self):
        bubble = self.make()
        sent = []
        bubble.submitted.connect(sent.append)
        bubble.input.setText("  olá  ")
        bubble.input.returnPressed.emit()
        self.assertEqual(sent, ["olá"])
        self.assertEqual(bubble.input.text(), "")

    def test_empty_message_is_not_sent(self):
        bubble = self.make()
        sent = []
        bubble.submitted.connect(sent.append)
        bubble.input.setText("   ")
        bubble.input.returnPressed.emit()
        self.assertEqual(sent, [])

    def test_goes_above_a_body_on_the_taskbar(self):
        bubble = self.make()
        area = QGuiApplication.primaryScreen().availableGeometry()
        body = QRect(area.center().x(), area.bottom() - 52, 48, 52)
        bubble.place_near(body)
        self.assertLess(bubble.y(), body.top())
        self.assertTrue(bubble.tail_below)

    def test_stays_inside_the_screen_at_the_edges(self):
        bubble = self.make()
        area = QGuiApplication.primaryScreen().availableGeometry()
        for x in (area.left(), area.right() - 48):
            bubble.place_near(QRect(x, area.bottom() - 52, 48, 52))
            self.assertGreaterEqual(bubble.x(), area.left())
            self.assertLessEqual(bubble.x() + bubble.width(), area.right() + 1)

    def test_history_is_limited(self):
        bubble = self.make()
        for number in range(40):
            bubble.add_user(str(number))
        self.assertLessEqual(len(bubble.turns), 14)
