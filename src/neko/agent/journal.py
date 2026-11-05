"""Diário da tela: só texto, um arquivo por dia e apagado depois do prazo. Nenhuma imagem é guardada."""
import json, logging, shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from ..memory.text import tokens

log = logging.getLogger(__name__)

MAX_TEXT = 4000
SAME_CONTENT = 0.85

@dataclass
class Snapshot:
    quando: datetime
    app: str
    titulo: str
    texto: str

    def trecho(self, limite=240):
        return " ".join(self.texto.split())[:limite]

class ScreenJournal:
    def __init__(self, folder: Path, retention_days=7):
        self.folder = folder
        self.retention_days = retention_days
        self.last_tokens = set()
        self.last_app = None

    def _path(self, day):
        return self.folder / f"{day.isoformat()}.jsonl"

    def add(self, snapshot):
        """Grava só o que mudou de verdade: a mesma tela com um detalhe a mais não vira outra entrada."""
        words = tokens(snapshot.texto)
        if snapshot.app == self.last_app and words and self.last_tokens:
            if len(words & self.last_tokens) / len(words | self.last_tokens) >= SAME_CONTENT:
                return False
        self.last_tokens, self.last_app = words, snapshot.app
        self.folder.mkdir(parents=True, exist_ok=True)
        record = {"t": snapshot.quando.isoformat(timespec="seconds"), "app": snapshot.app,
                  "titulo": snapshot.titulo, "texto": snapshot.texto[:MAX_TEXT]}
        with self._path(snapshot.quando.date()).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True

    def _read(self, day):
        path = self._path(day)
        if not path.exists():
            return []
        found = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and {"t", "app", "titulo", "texto"} <= record.keys():
                found.append(record)
        return found

    def days(self):
        return sorted(path.stem for path in self.folder.glob("*.jsonl")) if self.folder.is_dir() else []

    def search(self, query, days=None, limit=5):
        """Procura pelas palavras, das mais novas para as mais antigas."""
        wanted = tokens(query)
        if not wanted:
            return []
        scored = []
        for offset in range(days or self.retention_days):
            for record in self._read(date.today() - timedelta(days=offset)):
                score = len(wanted & tokens(f"{record['titulo']} {record['texto']}"))
                if score:
                    scored.append((score, record["t"], record))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [record for _, _, record in scored[:limit]]

    def at(self, hour, minute=0, day=None):
        """A entrada mais próxima de um horário."""
        target = hour * 60 + minute
        def distance(record):
            moment = datetime.fromisoformat(record["t"])
            return abs(moment.hour * 60 + moment.minute - target)
        entries = self._read(day or date.today())
        return min(entries, key=distance) if entries else None

    def purge(self):
        limit = (date.today() - timedelta(days=self.retention_days - 1)).isoformat()
        for name in self.days():
            if name < limit:
                self._path(date.fromisoformat(name)).unlink(missing_ok=True)

    def clear(self):
        if self.folder.exists():
            shutil.rmtree(self.folder, ignore_errors=True)
        self.last_tokens, self.last_app = set(), None
