"""Percebe padrões nos Downloads. Só nomes e extensões; o conteúdo nunca é lido sem a sua autorização."""
import logging
from pathlib import Path
from .memory.text import fold
from .reply import Confirmation, Reply
from .skills import files

log = logging.getLogger(__name__)

SUGGEST_AFTER = 3
WINDOW_DAYS = 30
EVENT_MANUAL = "zip_extraido_manual"

class DownloadTracker:
    """Compara fotos da pasta: um arquivo só conta depois de parar de crescer."""
    def __init__(self, folder):
        self.folder = Path(folder)
        self.known = set()
        self.sizes = {}
        self.zips = {}
        self.known = self._listing().keys() | set()
        self.zips = {fold(Path(name).stem): name for name in self.known if name.lower().endswith(".zip")}

    def _listing(self):
        found = {}
        try:
            for path in self.folder.iterdir():
                try:
                    found[path.name] = -1 if path.is_dir() else path.stat().st_size
                except OSError:
                    pass
        except OSError:
            log.warning("Não foi possível ler a pasta de downloads")
        return found

    def scan(self):
        """Devolve (arquivos novos completos, pastas novas que vieram de um zip já conhecido)."""
        listing = self._listing()
        new_files, extracted = [], []
        for name, size in listing.items():
            if name in self.known:
                continue
            if size == -1:
                self.known.add(name)
                if fold(name) in self.zips:
                    extracted.append(name)
                continue
            if Path(name).suffix.lower() in files.PARTIAL or size == 0:
                continue
            if self.sizes.get(name) == size:
                self.known.add(name)
                self.sizes.pop(name, None)
                new_files.append(self.folder / name)
                if name.lower().endswith(".zip"):
                    self.zips[fold(Path(name).stem)] = name
            else:
                self.sizes[name] = size
        self.known &= set(listing)
        return new_files, extracted

class Habits:
    def __init__(self, memory, config, skills, notify):
        self.memory, self.config, self.skills, self.notify = memory, config, skills, notify
        self.tracker = None
        self.own_extractions = set()

    @property
    def enabled(self):
        return self.config.get("watch_downloads", False) and not self.config.get("observation_paused", False)

    def start(self):
        self.tracker = DownloadTracker(files.known_folder("downloads"))

    def check(self):
        """Chamado por um temporizador; devolve os zips que devem ser tratados automaticamente."""
        if not self.enabled or self.tracker is None:
            return []
        new_files, extracted = self.tracker.scan()
        for path in new_files:
            self.memory.log("download", path.suffix.lower() or "sem extensão")
        for name in extracted:
            if fold(name) in self.own_extractions:
                self.own_extractions.discard(fold(name))
            else:
                self.memory.log(EVENT_MANUAL, "zip")
                self.maybe_suggest()
        return [path for path in new_files if path.suffix.lower() == ".zip"] if self._automatic() else []

    def _automatic(self):
        return self.config.get("automations", {}).get("extract_zip", False)

    def maybe_suggest(self):
        automations = self.config.get("automations", {})
        if automations.get("extract_zip") or automations.get("extract_zip_declined"):
            return
        count = len(self.memory.events(EVENT_MANUAL, WINDOW_DAYS))
        if count < SUGGEST_AFTER:
            return
        self.notify(Reply(f"Percebi uma coisa: você descompactou {count} arquivos .zip logo depois de baixar. "
                          "Quer que eu faça isso sozinho? Eu verifico com o Defender antes e depois, e pergunto antes de abrir.",
                          mood="curious", effect="sparkle",
                          confirm=Confirmation("Posso assumir essa tarefa?", self._accept, self._decline, "Pode sim", "Não, obrigado")))

    def _accept(self):
        self.config.data["automations"]["extract_zip"] = True
        self.config.save()
        self.memory.add_unchecked("preferences.md", "Quer que o Neku verifique e descompacte os .zip baixados", origin="conversa")
        return Reply("Fechado! Aprendi mais essa. Dá para desligar nas Configurações quando quiser.", mood="excited", effect="sparkle", xp=20)

    def _decline(self):
        self.config.data["automations"]["extract_zip_declined"] = True
        self.config.save()
        return Reply("Tudo bem, não pergunto de novo.", mood="neutral")

    def handle_zip(self, path, on_progress=None):
        """Roda fora da interface. Marca a pasta como obra do Neku para não contar como hábito."""
        self.own_extractions.add(fold(files.unique_path(path.with_suffix("")).name))
        self.skills.on_progress = on_progress or (lambda difficulty, text: None)
        return self.skills.process_zip(path)
