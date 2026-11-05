"""Os olhos do agente: captura a tela, esconde o que é privado e lê o texto, fora da thread da interface."""
import logging, threading, time
from datetime import datetime
from . import capture, privacy
from .journal import Snapshot
from .ocr import ScreenReader

log = logging.getLogger(__name__)

MIN_TEXT = 12

class VisionWorker(threading.Thread):
    def __init__(self, config, on_snapshot, should_pause, own_windows=lambda: ()):
        super().__init__(daemon=True, name="visao")
        self.config, self.on_snapshot, self.should_pause, self.own_windows = config, on_snapshot, should_pause, own_windows
        self.reader = ScreenReader()
        self.signature = None
        self.stopping = threading.Event()

    def settings(self):
        return self.config.get("vision", {})

    def run(self):
        while not self.stopping.wait(self.settings().get("interval_seconds", 8)):
            if self.should_pause():
                continue
            try:
                self.look()
            except Exception:
                log.exception("Falha ao ler a tela")

    def stop(self):
        self.stopping.set()

    def private(self, app, title):
        cfg = self.settings()
        return privacy.is_private(app, title, self.config.get("ignored_apps", []), cfg.get("ignored_titles", []))

    def look(self):
        """Um olhar. Devolve o que viu, ou None se nada mudou ou se não havia o que ler."""
        active = capture.foreground()
        if active is None:
            return None
        frame = capture.grab()
        for rect in self.own_windows():
            frame.hide(rect)
        for app, title, rect in capture.visible_windows():
            if self.private(app, title):
                frame.hide(rect)
        signature = frame.signature()
        if not capture.changed(self.signature, signature):
            return None
        self.signature = signature
        hidden = self.private(active[0], active[1])
        text = privacy.redact(self.reader.read(frame.pixels))
        if len(text) < MIN_TEXT:
            return None
        snapshot = Snapshot(datetime.now(), "privado" if hidden else active[0], "" if hidden else privacy.redact(active[1]), text)
        self.on_snapshot(snapshot)
        return snapshot
