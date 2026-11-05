"""Quem o Neku é: como reage à dificuldade e como evolui com o uso."""
import json, logging, os

log = logging.getLogger(__name__)

STAGES = ((0, "Filhote"), (60, "Curioso"), (200, "Parceiro"), (600, "Mestre"))

def reaction(difficulty, success):
    """Expressão e efeito para o fim de uma tarefa, conforme o tamanho do desafio."""
    if success:
        return {0: ("happy", None), 1: ("happy", None), 2: ("proud", "sparkle")}.get(difficulty, ("excited", "sparkle"))
    return ("confused", "question") if difficulty <= 1 else ("sad", "sweat")

def start_reaction(difficulty):
    if difficulty >= 3:
        return "working", "sweat", "Ufa, essa é pesada! Já estou nisso…"
    if difficulty == 2:
        return "working", "dots", "Deixa comigo, vai levar um instante…"
    return "thinking", "dots", ""

class Evolution:
    def __init__(self, root):
        self.path = root / "data" / "progress.json"
        self.xp = 0
        try:
            value = json.loads(self.path.read_text(encoding="utf-8")).get("xp", 0)
            self.xp = value if type(value) is int and value >= 0 else 0
        except (OSError, ValueError, AttributeError):
            pass

    @property
    def stage(self):
        return sum(1 for need, _ in STAGES if self.xp >= need)

    @property
    def name(self):
        return STAGES[self.stage - 1][1]

    @property
    def next_goal(self):
        return STAGES[self.stage][0] if self.stage < len(STAGES) else None

    def gain(self, amount):
        """Soma experiência e devolve o nome do novo estágio quando ele muda."""
        if amount <= 0:
            return None
        before = self.stage
        self.xp += amount
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps({"xp": self.xp}), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            log.exception("Não foi possível salvar o progresso")
        return self.name if self.stage > before else None
