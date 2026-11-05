import ctypes, logging, sys
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter

log = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
HOTKEY_ID = 0x4E4B

class GlobalHotkey(QAbstractNativeEventFilter):
    """Ctrl+Alt+N chama o Neku de qualquer lugar. Registra só esse atalho; nenhuma tecla é lida."""
    def __init__(self, app, callback):
        super().__init__()
        self.callback = callback
        self.registered = False
        if sys.platform != "win32":
            return
        self.registered = bool(ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("N")))
        if self.registered:
            app.installNativeEventFilter(self)
        else:
            log.warning("Atalho Ctrl+Alt+N indisponível: outro programa pode estar usando")

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.callback()
                return True, 0
        return False, 0

    def close(self):
        if self.registered:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            self.registered = False
