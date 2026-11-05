"""Abre o Neku de verdade em um processo próprio, sem janela e sem tocar no registro."""
import logging, sys, time
import helpers
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox
import neko.app as app

root, close_after_ms, start_chat = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3] == "chat"
logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(root / "child.log", encoding="utf-8")])

def notice(parent, title, text):
    print("AVISO:", text.splitlines()[0], flush=True)

app.autostart.sync = lambda *args, **kwargs: None
QMessageBox.information = staticmethod(notice)
QMessageBox.warning = staticmethod(notice)
original = app.NekoApp.__init__

def close(neko):
    print("FECHANDO", time.time(), flush=True)
    neko.quit()

def patched(neko, store, paths, base):
    original(neko, store, paths, base)
    neko.tray.icon.showMessage = lambda *args, **kwargs: None
    print("ABERTO", neko.pet.body.half_w * 2, flush=True)
    if start_chat:
        QTimer.singleShot(50, lambda: neko.chat.submit("olá"))
    QTimer.singleShot(close_after_ms, lambda: close(neko))

app.NekoApp.__init__ = patched
sys.exit(app.run(root))
