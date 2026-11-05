"""A conversa: balão, respostas fora da thread da interface e perguntas de confirmação."""
import logging, threading
from PySide6.QtCore import QObject, Signal
from .bubble import ChatBubble
from .character import start_reaction
from .reply import Reply

log = logging.getLogger(__name__)

ERROR_ANSWER = "Ops, algo deu errado por aqui e não consegui responder. Registrei o problema no log."

class ChatController(QObject):
    reply_ready = Signal(object)
    token_ready = Signal(str)
    notice_ready = Signal(object)
    progress_ready = Signal(int, str)

    def __init__(self, companion, body, evolution=None):
        """`body` é quem aparece: precisa de rect(), mood(humor, segundos) e activity(nome ou None)."""
        super().__init__()
        self.companion, self.body, self.evolution = companion, body, evolution
        self.bubble = ChatBubble()
        self.busy = False
        self.pending_confirm = None
        self.pending_is_offer = False
        self.bubble.submitted.connect(self.submit)
        self.bubble.answered.connect(self.answer_confirmation)
        self.reply_ready.connect(self.show_reply)
        self.token_ready.connect(self.bubble.append)
        self.notice_ready.connect(self.show_notice)
        self.progress_ready.connect(self.show_progress)

    def open(self):
        """Quem abre a conversa quer falar: uma oferta feita pelo Neku não pode tomar a caixa de texto."""
        if self.pending_is_offer:
            self.drop_offer()
        self.bubble.place_near(self.body.rect())
        self.bubble.open()
        self.body.mood("curious", 1.2)

    def drop_offer(self):
        """A oferta perdeu a vez. Perguntas sobre algo que você pediu nunca passam por aqui."""
        if self.pending_is_offer:
            self.pending_confirm, self.pending_is_offer = None, False
            self.bubble.clear_question()

    def expire_offer(self):
        if self.pending_is_offer:
            self.drop_offer()
            self.bubble.hide()

    def follow(self):
        if self.bubble.isVisible():
            self.bubble.place_near(self.body.rect())

    def close(self):
        self.bubble.close()

    def submit(self, text):
        if self.busy or self.bubble.waiting_answer:
            return
        self.bubble.add_user(text)
        self.busy = True
        self.body.activity("pensando")
        self.bubble.begin_answer()
        threading.Thread(target=self.respond_in_background, args=(text,), daemon=True).start()

    def respond_in_background(self, text):
        self._work(lambda: self.companion.respond(text, on_token=self.token_ready.emit, on_progress=self.progress_ready.emit))

    def _work(self, task):
        try:
            reply = task()
        except Exception:
            log.exception("Falha ao gerar a resposta")
            reply = Reply(ERROR_ANSWER, mood="sad")
        self.reply_ready.emit(reply)

    def show_progress(self, difficulty, text):
        _, _, line = start_reaction(difficulty)
        self.body.activity("trabalhando" if difficulty >= 2 else "pensando")
        message = text or line
        if message:
            self.bubble.append(message + "\n")

    def show_reply(self, reply):
        self.busy = False
        self.body.activity(None)
        self.bubble.replace_answer(reply.text)
        self._finish(reply)

    def show_notice(self, reply):
        """Mensagens por iniciativa do Neku: aparecem sem tirar o foco do que você está fazendo."""
        self.bubble.place_near(self.body.rect())
        self.bubble.say(reply.text)
        self.bubble.show_passive()
        self._finish(reply)
        self.pending_is_offer = reply.confirm is not None

    def _finish(self, reply):
        self.body.mood(reply.mood)
        evolved = self.evolution.gain(reply.xp) if self.evolution else None
        if evolved:
            self.bubble.append(f"\n\nSinto que aprendi muito… agora sou {evolved}! ✦")
            self.body.mood("excited", 5)
        if reply.confirm:
            self.pending_confirm = reply.confirm
            self.bubble.ask(reply.confirm.question, reply.confirm.yes_label, reply.confirm.no_label)
            self.bubble.place_near(self.body.rect())

    def answer_confirmation(self, accepted):
        confirm, self.pending_confirm = self.pending_confirm, None
        self.pending_is_offer = False
        if confirm is None:
            return
        action = confirm.on_yes if accepted else confirm.on_no
        if action is None:
            self.bubble.say("Tudo bem, deixei como estava.")
            self.body.mood("neutral")
            return
        self.busy = True
        self.body.activity("trabalhando")
        self.bubble.begin_answer()
        threading.Thread(target=self._work, args=(action,), daemon=True).start()
