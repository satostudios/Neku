from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
import json, sqlite3
from . import context
from .store import AddResult, ChangedOnDisk, MemoryFiles, contradicts, format_line, parse_entries, read_text, similar
from .text import tokens

PERSONAL_KINDS = ("fato", "preferência", "projeto", "temporário", "hipótese")

class Memory:
    def __init__(self, root: Path):
        self.memory_dir = root / "data" / "memory"
        self.diary_dir = root / "data" / "diary"
        self.db_path = root / "data" / "neko.sqlite3"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.diary_dir.mkdir(parents=True, exist_ok=True)
        self.files = MemoryFiles(self.memory_dir)
        self.files.create_missing()
        with closing(self._connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, created_at TEXT, kind TEXT, detail TEXT)")

    def _connect(self):
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def log(self, kind, detail, created_at=None):
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO events(created_at,kind,detail) VALUES(?,?,?)",
                       (created_at or datetime.now().isoformat(timespec="seconds"), kind, str(detail)[:300]))

    def events(self, kind=None, days=None):
        query, args = "SELECT created_at,kind,detail FROM events WHERE 1=1", []
        if kind:
            query += " AND kind=?"
            args.append(kind)
        if days:
            query += " AND created_at>=?"
            args.append((datetime.now() - timedelta(days=days)).isoformat(timespec="seconds"))
        with closing(self._connect()) as db:
            return db.execute(query + " ORDER BY id", args).fetchall()

    def purge_events(self, days):
        limit = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM events WHERE created_at<?", (limit,))

    def clear_events(self):
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM events")

    def export_events(self, path):
        rows = [dict(zip(("quando", "tipo", "detalhe"), row)) for row in self.events()]
        Path(path).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(rows)

    def diary(self, text):
        path = self.diary_dir / (datetime.now().strftime("%Y-%m-%d") + ".md")
        with path.open("a", encoding="utf-8") as f:
            f.write("\n## " + datetime.now().strftime("%H:%M") + "\n\n" + text + "\n")

    def entries(self, include_expired=False):
        return self.files.entries(include_expired)

    def personal_entries(self):
        return [entry for entry in self.entries() if entry.kind in PERSONAL_KINDS]

    def context_for(self, query, budget=context.DEFAULT_BUDGET):
        return context.select(self.entries(), query, budget)

    def find(self, query):
        wanted = tokens(query)
        scored = [(len(wanted & tokens(entry.text)), entry) for entry in self.personal_entries()]
        return [entry for score, entry in sorted(scored, key=lambda s: -s[0]) if score]

    def add(self, name, text, origin="conversa", until=None):
        clean = " ".join(text.split())
        known = self.personal_entries()
        for entry in known:
            if contradicts(clean, entry.text):
                return AddResult("conflict", other=entry)
        for entry in known:
            if similar(clean, entry.text):
                return AddResult("duplicate", other=entry)
        return self.add_unchecked(name, clean, origin, until)

    def add_unchecked(self, name, text, origin="conversa", until=None):
        self.files.append(name, format_line(text, origin, until=until))
        saved = [entry for entry in parse_entries(name, read_text(self.files.path(name))[0]) if entry.text == text]
        self.log("memory_write", name)
        return AddResult("saved", entry=saved[-1] if saved else None)

    def remove(self, entry):
        self.files.remove(entry)
        self.log("memory_remove", entry.name)

    def replace(self, entry, new_text):
        self.files.replace(entry, " ".join(new_text.split()))
        self.log("memory_replace", entry.name)

    def _fresh(self, entry):
        """Reencontra a linha pelo conteúdo: outra alteração pode ter deslocado o índice."""
        for candidate in self.entries(include_expired=True):
            if candidate.name == entry.name and candidate.raw == entry.raw:
                return candidate
        raise ChangedOnDisk(entry.name)

    def remove_all(self, entries):
        for entry in entries:
            self.remove(self._fresh(entry))

    def replace_all(self, changes):
        for entry, new_text in changes:
            self.replace(self._fresh(entry), new_text)

    def ensure_file(self, name):
        self.files.ensure_file(name)

    def read_file(self, name):
        return self.files.read_file(name)

    def save_file(self, name, text, expected_mtime):
        return self.files.save_file(name, text, expected_mtime)
