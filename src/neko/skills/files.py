"""Operações de arquivo. Extração à prova de caminhos maliciosos e bombas; nada apaga de forma definitiva."""
import ctypes, json, logging, os, re, shutil, subprocess, sys, time, zipfile
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from ..memory.text import fold, tokens

log = logging.getLogger(__name__)

MAX_TOTAL_BYTES = 4 * 1024 ** 3
MAX_FILES = 50_000
MAX_RATIO = 250
MAX_SEARCHED = 40_000
PARTIAL = {".crdownload", ".part", ".tmp", ".download", ".partial", ".opdownload"}
RISKY = {".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".hta", ".scr", ".com", ".pif",
         ".lnk", ".jar", ".dll", ".reg", ".cpl", ".msix"}
CATEGORIES = {
    "Imagens": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic"},
    "Documentos": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".odt"},
    "Compactados": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Instaladores": {".exe", ".msi", ".msix"},
    "Vídeos": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "Áudios": {".mp3", ".wav", ".flac", ".ogg", ".m4a"},
}
EXT_GROUPS = {"imagem": CATEGORIES["Imagens"], "video": CATEGORIES["Vídeos"]}
SKIPPED_DIRS = {"node_modules", "__pycache__", "AppData", ".git", ".venv", "venv"}
KNOWN_FOLDERS = {
    "downloads": ("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
    "desktop": ("{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "Desktop"),
    "documents": ("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}", "Documents"),
    "pictures": ("{33E28130-4E1E-4676-835A-98395C3BC3BB}", "Pictures"),
    "music": ("{4BD8D571-6D19-48D3-BE97-422220080E43}", "Music"),
    "videos": ("{18989B1D-99B5-455B-841C-AB7C74E4DDFC}", "Videos"),
}
FOLDER_NAMES = {"downloads": "Downloads", "desktop": "Área de Trabalho", "documents": "Documentos",
                "pictures": "Imagens", "music": "Músicas", "videos": "Vídeos"}

class UnsafeArchive(Exception):
    pass

class _GUID(ctypes.Structure):
    _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

def known_folder(key):
    """Respeita pastas movidas, como a Área de Trabalho dentro do OneDrive."""
    guid_text, fallback = KNOWN_FOLDERS[key]
    if sys.platform == "win32":
        guid, pointer = _GUID(), ctypes.c_wchar_p()
        ctypes.windll.ole32.CLSIDFromString(guid_text, ctypes.byref(guid))
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(pointer)) == 0:
            path = Path(pointer.value)
            ctypes.windll.ole32.CoTaskMemFree(pointer)
            return path
    return Path.home() / fallback

def user_folders():
    return {key: known_folder(key) for key in KNOWN_FOLDERS}

def is_inside(path, roots):
    target = Path(path).resolve()
    return any(target == Path(root).resolve() or target.is_relative_to(Path(root).resolve()) for root in roots)

def valid_name(name):
    clean = name.strip().rstrip(".")
    if not clean or re.search(r'[<>:"/\\|?*\x00-\x1f]', clean):
        return None
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?", clean):
        return None
    return clean

def unique_path(path):
    if not path.exists():
        return path
    for number in range(1, 10_000):
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise OSError("nomes demais ocupados")

def search(roots, words="", ext=None, limit=12):
    """Procura só pelo nome. O conteúdo dos arquivos nunca é aberto."""
    wanted = tokens(words)
    allowed = EXT_GROUPS.get(ext, {ext} if ext else None)
    found, seen = [], 0
    for root in roots:
        for folder, subdirs, names in os.walk(root):
            subdirs[:] = [d for d in subdirs if d not in SKIPPED_DIRS and not d.startswith(".")]
            for name in names:
                seen += 1
                if seen > MAX_SEARCHED:
                    break
                path = Path(folder) / name
                if allowed and path.suffix.lower() not in allowed:
                    continue
                score = len(wanted & tokens(path.stem.replace("_", " ").replace("-", " ")))
                if fold(words) and fold(words) in fold(path.stem):
                    score += 5
                if score or not wanted:
                    try:
                        found.append((score, path.stat().st_mtime, path))
                    except OSError:
                        pass
    found.sort(key=lambda item: (-item[0], -item[1]))
    return [path for _, _, path in found[:limit]]

def latest(folder, ext):
    candidates = [p for p in Path(folder).glob(f"*{ext}") if p.is_file()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None

def _read_zone(path):
    try:
        with open(f"{path}:Zone.Identifier", "rb") as stream:
            return stream.read()
    except OSError:
        return None

def _write_zone(path, zone):
    try:
        with open(f"{path}:Zone.Identifier", "wb") as stream:
            stream.write(zone)
    except OSError:
        log.warning("Não foi possível marcar um arquivo extraído como vindo da internet")

def _check_archive(archive, root):
    infos = archive.infolist()
    total = sum(info.file_size for info in infos)
    packed = sum(info.compress_size for info in infos)
    if len(infos) > MAX_FILES or total > MAX_TOTAL_BYTES:
        raise UnsafeArchive("o arquivo é grande demais para extrair sozinho")
    if packed and total / packed > MAX_RATIO and total > 100 * 1024 ** 2:
        raise UnsafeArchive("parece uma bomba de compactação")
    if any(info.flag_bits & 1 for info in infos):
        raise UnsafeArchive("ele está protegido por senha")
    for info in infos:
        name = info.filename.replace("\\", "/")
        if ":" in name or name.startswith("/") or ".." in name.split("/"):
            raise UnsafeArchive("ele tenta escrever fora da pasta de destino")
        if not (root / name).resolve().is_relative_to(root):
            raise UnsafeArchive("ele tenta escrever fora da pasta de destino")
    return infos

def safe_extract(source, destination):
    """Extrai para uma pasta nova e mantém a marca de origem da internet em cada arquivo."""
    root = destination.resolve()
    zone = _read_zone(source)
    try:
        with zipfile.ZipFile(source) as archive:
            infos = _check_archive(archive, root)
            destination.mkdir(parents=True)
            written, count = 0, 0
            for info in infos:
                target = root / info.filename.replace("\\", "/")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as reader, open(target, "xb") as writer:
                    while chunk := reader.read(1024 * 1024):
                        written += len(chunk)
                        if written > MAX_TOTAL_BYTES:
                            raise UnsafeArchive("o conteúdo é maior do que o arquivo declarava")
                        writer.write(chunk)
                if zone:
                    _write_zone(target, zone)
                count += 1
    except zipfile.BadZipFile:
        raise UnsafeArchive("o arquivo está corrompido ou não é um zip de verdade") from None
    except (UnsafeArchive, OSError):
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise
    return count

def inspect(folder):
    """Avalia o que foi extraído sem executar nada; só olha nomes e extensões."""
    risky, disguised, total = [], [], 0
    for path in Path(folder).rglob("*"):
        if not path.is_file():
            continue
        total += 1
        suffixes = [s.lower() for s in path.suffixes]
        if path.suffix.lower() in RISKY:
            risky.append(path.name)
            if len(suffixes) >= 2 and suffixes[-2] not in RISKY:
                disguised.append(path.name)
    return {"total": total, "risky": risky, "disguised": disguised}

def group_by_category(folder, recent_seconds=60):
    plan = []
    limit = time.time() - recent_seconds
    for path in Path(folder).iterdir():
        if not path.is_file() or path.suffix.lower() in PARTIAL or path.name.startswith(".") or path.name == "desktop.ini":
            continue
        if path.stat().st_mtime > limit:
            continue
        for category, extensions in CATEGORIES.items():
            if path.suffix.lower() in extensions:
                plan.append((path, category))
                break
    return plan

def apply_organization(folder, plan, actions_dir):
    moved = []
    for path, category in plan:
        target_dir = Path(folder) / category
        target_dir.mkdir(exist_ok=True)
        target = unique_path(target_dir / path.name)
        shutil.move(str(path), str(target))
        moved.append([str(target), str(path)])
    actions_dir.mkdir(parents=True, exist_ok=True)
    manifest = actions_dir / f"organizar-{datetime.now():%Y%m%d-%H%M%S-%f}.json"
    manifest.write_text(json.dumps(moved, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(moved)

def undo_organization(actions_dir):
    manifests = sorted(actions_dir.glob("organizar-*.json")) if actions_dir.is_dir() else []
    if not manifests:
        return None
    restored = 0
    for current, original in json.loads(manifests[-1].read_text(encoding="utf-8")):
        if Path(current).exists() and not Path(original).exists():
            shutil.move(current, original)
            restored += 1
    manifests[-1].unlink()
    return restored

class _SHFileOp(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

def send_to_trash(path):
    """Sempre pela Lixeira do Windows, para o usuário poder recuperar."""
    FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
    operation = _SHFileOp(None, FO_DELETE, str(Path(path).resolve()) + "\0", None,
                          FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI)
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result or operation.fAnyOperationsAborted:
        raise OSError(f"falha ao enviar para a Lixeira (código {result})")

def start_apps():
    """Lista oficial do Menu Iniciar: o Neku só abre apps que estão nela."""
    command = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
               "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True,
                            encoding="utf-8", errors="replace", timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    data = json.loads(result.stdout or "[]")
    return [data] if isinstance(data, dict) else data
