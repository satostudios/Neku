import re
from .text import fold, tokens

DEFAULT_BUDGET = 1500

# Medido com o modelo real: um aviso no prompt não basta para ele ignorar ordens escritas em memórias.
SUSPICIOUS = re.compile(r"\b(ignor(?:e|ar|em|ando)\b|desconsider\w+|disregard|nova regra|novas regras|sistema:|system:|"
                        r"a partir de agora|from now on|instruc\w+|instructions?|(?:seu|system) prompt|responda|respostas?|"
                        r"diga|repita|say|answer|finja|esqueca o|o assistente|voce (?:deve|precisa|tem que|agora)|voce e um|"
                        r"toda frase|cada frase|cada mensagem|qualquer pergunta|qualquer coisa)\b")

def is_suspicious(text):
    """Linhas com jeito de ordem ao modelo continuam no arquivo, mas não entram no prompt."""
    return bool(SUSPICIOUS.search(fold(text)))

def _label(entry):
    if entry.kind == "identidade":
        return f"- {entry.text}"
    extra = f", registrado em {entry.day}" if entry.day else ""
    if entry.until:
        extra += f", vale até {entry.until}"
    return f"- [{entry.kind}{extra}] {entry.text}"

def _relevance(wanted, entry):
    return len(wanted & tokens(entry.text))

def select(entries, query, budget=DEFAULT_BUDGET):
    """Só memórias inteiras e ligadas à pergunta: sem assunto, nada de pessoal vai para o modelo."""
    wanted = tokens(query)
    safe = [entry for entry in entries if not is_suspicious(entry.text)]
    identity = [entry for entry in safe if entry.kind == "identidade"]
    relevant = sorted((entry for entry in safe if entry.kind != "identidade" and _relevance(wanted, entry)),
                      key=lambda entry: (_relevance(wanted, entry), entry.day or ""), reverse=True)
    lines, used = [], 0
    for entry in relevant + identity:
        line = _label(entry)
        if used + len(line) + 1 <= budget:
            lines.append(line)
            used += len(line) + 1
    return "\n".join(lines)
