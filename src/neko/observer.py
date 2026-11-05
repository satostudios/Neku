import os, sys, ctypes
from ctypes import wintypes
from datetime import datetime
import psutil

ALWAYS_IGNORED = {"python.exe","pythonw.exe","pythonw3.11.exe","neko.exe","llama-server.exe"}

def rounded_quarter(moment):
    """Só horários aproximados: a observação nunca guarda precisão de minuto."""
    return moment.replace(minute=moment.minute - moment.minute % 15, second=0, microsecond=0)

class Observer:
    def __init__(self, memory, config=None):
        self.memory, self.config, self.last = memory, config, None
        if config:
            memory.purge_events(config.get("observation_retention_days", 30))

    def ignored(self):
        names = self.config.get("ignored_apps", []) if self.config else []
        return ALWAYS_IGNORED | {str(name).lower() for name in names}

    def poll(self):
        if sys.platform != "win32":
            return None
        try:
            u = ctypes.windll.user32
            hwnd = u.GetForegroundWindow()
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            exe = os.path.basename(psutil.Process(pid.value).exe())
            if exe.lower() in self.ignored():
                return None
            quarter = rounded_quarter(datetime.now())
            key = (exe, quarter)
            if key != self.last:
                self.last = key
                self.memory.log("foreground_app", exe, quarter.isoformat(timespec="minutes"))
                return exe
        except (OSError, psutil.Error, AttributeError, ValueError):
            return None
        return None
