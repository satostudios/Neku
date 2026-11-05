import logging, os, sys
from pathlib import Path

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "NekoAI"

def command(root):
    pyw = root/".venv"/"Scripts"/"pythonw.exe"
    if not pyw.exists(): pyw = Path(sys.executable)
    return f'"{pyw}" "{root/"src"/"main.py"}"'

def legacy_file():
    # A v0.1 usava um .bat em UTF-8, que falha em pastas com acento.
    appdata = os.environ.get("APPDATA")
    if not appdata: return None
    return Path(appdata)/"Microsoft/Windows/Start Menu/Programs/Startup"/"NekoAI.bat"

def is_registered():
    if sys.platform!="win32": return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except FileNotFoundError:
        return False

def sync(root, enabled):
    if sys.platform!="win32": return
    import winreg
    legacy = legacy_file()
    if legacy and legacy.exists():
        legacy.unlink()
        log.info("Inicialização antiga (.bat) removida")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command(root))
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
                log.info("Inicialização com o Windows desligada")
            except FileNotFoundError:
                pass
