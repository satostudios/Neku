import faulthandler, importlib.metadata, json, logging, os, platform, struct, sys, threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit
from . import __version__, autostart
from .llm import is_local_endpoint
from .permissions import CAPABILITIES, LEVEL_NAMES

log = logging.getLogger(__name__)

LOG_MAX_BYTES = 512_000
LOG_BACKUPS = 3
CRASH_MAX_BYTES = 1_000_000
ERROR_MESSAGE = "O Neku encontrou um erro inesperado.\n\nOs detalhes estão em:\n{}"

_crash_file = None
_log_path = None
_notified = False

def setup(root):
    global _crash_file, _log_path
    logs = root/"logs"
    try:
        logs.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(logs/"neko.log", maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS,
                                      encoding="utf-8", delay=True)
        crash = logs/"crash.log"
        mode = "w" if crash.exists() and crash.stat().st_size > CRASH_MAX_BYTES else "a"
        _crash_file = crash.open(mode, encoding="utf-8")
        faulthandler.enable(file=_crash_file)
        _log_path = logs/"neko.log"
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    sys.excepthook = handle_exception
    threading.excepthook = lambda args: handle_exception(args.exc_type, args.exc_value, args.exc_traceback)

def handle_exception(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        return
    log.critical("Erro não tratado", exc_info=(exc_type, exc, tb))
    notify_error()

def notify_error():
    # Avisa uma vez só: um erro em paintEvent se repetiria a cada quadro.
    global _notified
    if _notified: return
    _notified = True
    show_error(ERROR_MESSAGE.format(_log_path or "(sem arquivo de log)"))

def show_error(message):
    if sys.platform=="win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "Neku", 0x10)

def _system_name():
    if sys.platform!="win32": return platform.platform()
    # O Python 3.11 ainda informa "Windows 10" no Windows 11; o build é quem distingue.
    version = sys.getwindowsversion()
    return f"Windows {'11' if version.build >= 22000 else version.major} (build {version.build})"

def _mask(path):
    text, home = str(path), str(Path.home())
    if text.lower().startswith(home.lower()):
        return "%USERPROFILE%" + text[len(home):]
    return text

def _version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "não instalado"

def _settings(root):
    try:
        data = json.loads((root/"config"/"settings.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None

def _on_off(value):
    return "ligado" if value else "desligado"

def _section(settings, key):
    value = settings.get(key)
    return value if isinstance(value, dict) else {}

def _installed_model(root):
    found = sorted((root/"models").glob("*.gguf")) if (root/"runtime"/"llama"/"llama-server.exe").exists() else []
    return found[0].stem if found else None

def _llm_line(settings, model=None):
    llm = settings.get("llm")
    if not isinstance(llm, dict): return "configuração inválida"
    endpoint = llm.get("endpoint")
    if not isinstance(endpoint, str) or not is_local_endpoint(endpoint):
        return f"{_on_off(llm.get('enabled'))}; endpoint RECUSADO (não é loopback)"
    if model and llm.get("use_bundled", True):
        return f"modelo embutido {model}, ligado sob demanda"
    return f"{_on_off(llm.get('enabled'))}; endpoint local {urlsplit(endpoint).netloc}"

def _dir_line(path):
    return f"{_mask(path)} ({'existe' if path.is_dir() else 'não existe'})"

def _log_size(path):
    return f"{path.stat().st_size/1024:.1f} KB" if path.exists() else "vazio"

def report(root):
    settings = _settings(root)
    lines = [f"Neku {__version__} - diagnóstico", "",
             f"Sistema: {_system_name()}",
             f"Python: {platform.python_version()} ({struct.calcsize('P')*8} bits)",
             f"Executável: {_mask(sys.executable)}", "", "Dependências:",
             f"  PySide6-Essentials: {_version('PySide6-Essentials')}",
             f"  psutil: {_version('psutil')}", f"  numpy: {_version('numpy')}", f"  pywin32: {_version('pywin32')}",
             f"  OCR do Windows: {_version('winrt-Windows.Media.Ocr')}", "", "Caminhos:",
             f"  Projeto: {_dir_line(root)}",
             f"  Memória: {_dir_line(root/'data'/'memory')}",
             f"  Diário: {_dir_line(root/'data'/'diary')}",
             f"  Logs: {_dir_line(root/'logs')} - neko.log {_log_size(root/'logs'/'neko.log')}",
             "", "Permissões:"]
    if settings is None:
        lines.append("  settings.json ausente ou inválido; o Neku usará os padrões ao abrir")
    else:
        lines += [f"  Ler a tela: {_on_off(_section(settings, 'vision').get('enabled'))}",
                  f"  Guardar mensagens no diário: {_on_off(settings.get('save_chat_history'))}",
                  f"  Observar nome do app ativo: {_on_off(settings.get('monitor_active_app'))}",
                  f"  Iniciar com o Windows: {_on_off(settings.get('start_with_windows'))}",
                  f"  Acompanhar Downloads: {_on_off(settings.get('watch_downloads'))}",
                  f"  Aprender linguajar: {_on_off(settings.get('learn_language', True))}",
                  f"  Seguir o mouse: {_on_off(settings.get('follow_mouse', True))}",
                  f"  Automação de .zip: {_on_off(_section(settings, 'automations').get('extract_zip'))}",
                  f"  LLM local: {_llm_line(settings, _installed_model(root))}"]
        lines += [f"  {label}: {LEVEL_NAMES.get(_section(settings, 'permissions').get(key, 'ask'), 'inválido')}"
                  for key, label in CAPABILITIES.items()]
    model = _installed_model(root)
    lines += [f"  Registro de inicialização presente: {'sim' if autostart.is_registered() else 'não'}",
              f"  Modelo local instalado: {'sim' if model else 'não'}",
              "  Comandos livres de terminal: não existem"]
    return "\n".join(lines)
