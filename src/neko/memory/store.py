import difflib, logging, os, re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from .text import fold, tokens

log = logging.getLogger(__name__)

BACKUPS_PER_FILE = 20
EXTRA_FILES = {"linguajar.md": "# Meu linguajar\n\nAinda não aprendi nenhuma expressão sua.\n"}
TEMPORARY_DAYS = 7
DUPLICATE_RATIO = 0.9

TEMPLATES = {
    "identity.md": "# Identidade do Neku\n\nSou Neku, um agente de IA local.\n",
    "personality.md": "# Personalidade\n\n- Curioso\n- Prestativo\n- Brincalhão\n",
    "user_profile.md": "# Perfil do usuário\n\nInformações compartilhadas explicitamente.\n",
    "preferences.md": "# Preferências\n\nPreferências confirmadas pelo usuário.\n",
    "projects.md": "# Projetos\n\nProjetos em andamento que o usuário pediu para lembrar.\n",
    "temporary.md": "# Observações temporárias\n\nAnotações de curto prazo; deixam de valer na data indicada.\n",
    "learned_behaviors.md": "# Comportamentos aprendidos\n\nPadrões observados com permissão; são hipóteses.\n",
    "important_memories.md": "# Memórias importantes\n\nFatos confirmados pelo usuário.\n",
}
FILE_KINDS = {
    "user_profile.md": "fato", "important_memories.md": "fato", "preferences.md": "preferência",
    "projects.md": "projeto", "temporary.md": "temporário", "learned_behaviors.md": "hipótese",
    "identity.md": "identidade", "personality.md": "identidade",
}
TEMPLATE_PROSE = {line for name, body in TEMPLATES.items() if name != "identity.md" for line in body.splitlines()
                  if line and not line.startswith(("#", "- "))}

SUFFIX = re.compile(r"\s+\((?P<origin>conversa|manual|observação),\s*(?P<day>\d{4}-\d{2}-\d{2})"
                    r"(?:,\s*até\s*(?P<until>\d{4}-\d{2}-\d{2}))?\)\s*$")
LEGACY_SUFFIX = re.compile(r"\s+\(registrado em (?P<day>\d{4}-\d{2}-\d{2})\)\s*$")
NEGATION = re.compile(r"\b(nao|nunca|jamais)\b")
KEYED_FACT = re.compile(r"^(?:eu\s+)?((?:meu|minha)\s+\w+(?:\s+\w+)?\s+(?:e|sao)|moro em|me chamo|trabalho (?:na|no|em))\s+(.+)$")

@dataclass(frozen=True)
class Entry:
    name: str
    index: int
    raw: str
    text: str
    origin: str = "manual"
    day: str = None
    until: str = None

    @property
    def kind(self):
        return FILE_KINDS.get(self.name, "fato")

    def expired(self, today=None):
        if not self.until:
            return False
        return self.until < (today or date.today()).isoformat()

@dataclass
class AddResult:
    status: str
    entry: Entry = None
    other: Entry = None

class ChangedOnDisk(Exception):
    pass

def read_text(path):
    """Lê sem alterar quebras de linha. Arquivos ANSI do Bloco de Notas antigo são aceitos."""
    raw = path.read_bytes()
    try:
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig"), "utf-8-sig"
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace"), "cp1252"

def write_text(path, text, encoding):
    target = "utf-8" if encoding == "cp1252" else encoding
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode(target))
    os.replace(tmp, path)

def split_lines(text):
    return re.split(r"(?<=\n)", text) if text else []

def newline_of(text):
    return "\r\n" if "\r\n" in text else "\n"

def parse_line(name, index, line):
    raw = line.rstrip("\r\n")
    stripped = raw.strip()
    if not stripped or stripped.startswith("#") or stripped in TEMPLATE_PROSE:
        return None
    body = re.sub(r"^[-*]\s+", "", stripped)
    match = SUFFIX.search(body)
    if match:
        return Entry(name, index, raw, body[:match.start()].strip(), match["origin"], match["day"], match["until"])
    match = LEGACY_SUFFIX.search(body)
    if match:
        return Entry(name, index, raw, body[:match.start()].strip(), "conversa", match["day"])
    return Entry(name, index, raw, body)

def parse_entries(name, text):
    found = (parse_line(name, i, line) for i, line in enumerate(split_lines(text)))
    return [entry for entry in found if entry and entry.text]

def format_line(text, origin="conversa", day=None, until=None):
    suffix = f"{origin}, {day or date.today().isoformat()}"
    if until:
        suffix += f", até {until}"
    return f"- {text} ({suffix})"

def similar(a, b):
    wanted, have = tokens(a), tokens(b)
    if not wanted or not have or len(wanted & have) / len(wanted | have) < 0.5:
        return False
    return difflib.SequenceMatcher(None, fold(a), fold(b)).ratio() >= DUPLICATE_RATIO

def contradicts(new, old):
    a, b = fold(new), fold(old)
    if bool(NEGATION.search(a)) != bool(NEGATION.search(b)):
        return NEGATION.sub("", a).split() == NEGATION.sub("", b).split()
    first, second = KEYED_FACT.match(a), KEYED_FACT.match(b)
    return bool(first and second and first[1] == second[1] and first[2] != second[2])

class MemoryFiles:
    def __init__(self, folder: Path):
        self.folder = folder
        self.backup_dir = folder / ".backup"

    def path(self, name):
        if name not in TEMPLATES and name not in EXTRA_FILES:
            raise ValueError(f"arquivo de memória desconhecido: {name}")
        return self.folder / name

    def create_missing(self):
        for name, body in TEMPLATES.items():
            path = self.folder / name
            if not path.exists():
                path.write_text(body, encoding="utf-8")

    def entries(self, include_expired=False):
        found = []
        for name in TEMPLATES:
            path = self.folder / name
            if path.exists():
                found += parse_entries(name, read_text(path)[0])
        return found if include_expired else [entry for entry in found if not entry.expired()]

    def backup(self, name):
        path = self.path(name)
        self.backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = self.backup_dir / f"{path.stem}.{stamp}.md"
        target.write_bytes(path.read_bytes())
        for old in sorted(self.backup_dir.glob(f"{path.stem}.*.md"))[:-BACKUPS_PER_FILE]:
            old.unlink()
        return target

    def append(self, name, line):
        path = self.path(name)
        text, encoding = read_text(path)
        if encoding == "cp1252":
            self.backup(name)
        newline = newline_of(text)
        if text and not text.endswith("\n"):
            text += newline
        write_text(path, text + line + newline, encoding)

    def _rewrite(self, entry, new_line):
        path = self.path(entry.name)
        text, encoding = read_text(path)
        lines = split_lines(text)
        if entry.index >= len(lines) or lines[entry.index].rstrip("\r\n") != entry.raw:
            raise ChangedOnDisk(entry.name)
        self.backup(entry.name)
        if new_line is None:
            del lines[entry.index]
        else:
            ending = lines[entry.index][len(entry.raw):]
            lines[entry.index] = new_line + ending
        write_text(path, "".join(lines), encoding)

    def remove(self, entry):
        self._rewrite(entry, None)

    def replace(self, entry, new_text):
        self._rewrite(entry, format_line(new_text, "conversa", until=entry.until))

    def ensure_file(self, name):
        path = self.path(name)
        if not path.exists():
            path.write_text(EXTRA_FILES.get(name, TEMPLATES.get(name, "")), encoding="utf-8")

    def read_file(self, name):
        path = self.path(name)
        return read_text(path)[0], path.stat().st_mtime_ns

    def save_file(self, name, text, expected_mtime):
        path = self.path(name)
        if path.stat().st_mtime_ns != expected_mtime:
            raise ChangedOnDisk(name)
        encoding = read_text(path)[1]
        if text == read_text(path)[0]:
            return expected_mtime
        self.backup(name)
        write_text(path, text, encoding)
        return path.stat().st_mtime_ns

def expiry_date(days=TEMPORARY_DAYS):
    return (date.today() + timedelta(days=days)).isoformat()
