"""O que ele aprende olhando você: fluxos entre programas e assuntos que se repetem."""
import json, logging, os
from collections import Counter
from datetime import date
from ..memory.commands import is_secret
from ..memory.text import STOPWORDS, fold

log = logging.getLogger(__name__)

MIN_REPEATS = 4
MIN_SHARE = 0.6
TOPIC_HYPOTHESIS = 30
MIN_DAYS = 2
MAX_TOPICS = 400
IGNORED_WORDS = frozenset("arquivo editar exibir inserir layout janela ajuda pagina inicio pesquisar buscar word excel "
                          "windows microsoft google chrome salvar fechar abrir novo nova".split())

class Learned:
    """Guarda contagens em um arquivo legível; apagar o arquivo apaga o aprendizado."""
    def __init__(self, path):
        self.path = path
        self.flows = {}
        self.topics = {}
        self.last_app = None
        self.dirty = False
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            flows, topics = data.get("fluxos", {}), data.get("assuntos", {})
        except (OSError, ValueError, AttributeError):
            return
        if isinstance(flows, dict) and isinstance(topics, dict):
            self.flows = {str(k): dict(v) for k, v in flows.items() if isinstance(v, dict)}
            self.topics = {str(k): dict(v) for k, v in topics.items() if isinstance(v, dict)}

    def save(self):
        if not self.dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps({"fluxos": self.flows, "assuntos": self.topics}, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
            self.dirty = False
        except OSError:
            log.exception("Não foi possível salvar o que foi aprendido")

    def observe_app(self, app):
        """Conta qual programa costuma vir depois de qual."""
        if not app or app == "privado" or app == self.last_app:
            return
        if self.last_app:
            following = self.flows.setdefault(self.last_app, {})
            following[app] = following.get(app, 0) + 1
            self.dirty = True
        self.last_app = app

    def next_app(self, app):
        """O programa que costuma vir depois deste, se o hábito já estiver firme."""
        following = self.flows.get(app, {})
        total = sum(following.values())
        if not following:
            return None
        best, count = max(following.items(), key=lambda item: item[1])
        return best if count >= MIN_REPEATS and count / total >= MIN_SHARE else None

    def observe_text(self, text):
        """Conta assuntos por dia. Mensagens com jeito de dado sensível ficam de fora."""
        if is_secret(text):
            return
        today = date.today().isoformat()
        words = Counter(word for word in fold(text).split() if word.isalpha() and 5 <= len(word) <= 16
                        and word not in STOPWORDS and word not in IGNORED_WORDS)
        for word in set(words):
            entry = self.topics.setdefault(word, {"total": 0, "dias": []})
            entry["total"] += 1
            if today not in entry["dias"]:
                entry["dias"] = (entry["dias"] + [today])[-14:]
        if len(self.topics) > MAX_TOPICS:
            kept = sorted(self.topics.items(), key=lambda item: item[1]["total"], reverse=True)[:MAX_TOPICS // 2]
            self.topics = dict(kept)
        self.dirty = True

    def top_topics(self, limit=8):
        ranked = sorted(self.topics.items(), key=lambda item: item[1]["total"], reverse=True)
        return [word for word, entry in ranked[:limit] if entry["total"] >= 3]

    def new_hypotheses(self, known):
        """Assuntos firmes viram hipóteses, nunca fatos: ficam em learned_behaviors.md, onde você pode apagar."""
        return [word for word, entry in self.topics.items()
                if entry["total"] >= TOPIC_HYPOTHESIS and len(entry["dias"]) >= MIN_DAYS and word not in known]
