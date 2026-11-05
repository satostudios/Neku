"""O que vale a pena notar na tela. Só gera ideias; quem decide se fala é a rede neural."""
import re
from dataclasses import dataclass
from ..memory.text import fold

ERROR = re.compile(r"traceback \(most recent call|\b\w*(?:error|exception)\b\s*:|\berro\b\s*:|\bfalha\b\s*:|"
                   r"\bfailed\b|\bfalhou\b|\bnot found\b|\bnao encontrad[oa]\b|\baccess denied\b|\bacesso negado\b")
LONG_TEXT = 1500

@dataclass
class Insight:
    kind: str
    detail: str

def find_error(text):
    """A linha que parece um erro; prefere a mais específica, com o nome da exceção."""
    best = None
    for line in text.splitlines():
        folded = fold(line)
        if ERROR.search(folded):
            if re.search(r"(error|exception)\s*:", folded):
                return line.strip()[:140]
            best = best or line.strip()[:140]
    return best

def detect(snapshot):
    found = []
    error = find_error(snapshot.texto)
    if error:
        found.append(Insight("erro", error))
    if len(snapshot.texto) >= LONG_TEXT:
        found.append(Insight("resumo", snapshot.titulo or snapshot.app))
    return found
