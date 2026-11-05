"""Pedidos sobre a tela. Só leem o que o usuário digitou: texto visto na tela nunca vira comando."""
import re
from dataclasses import dataclass
from ..memory.text import fold

LEAD = r"^(?:nek[ou][,:]?\s+)?(?:por favor[,:]?\s+)?(?:(?:voce\s+|vc\s+)?pode\s+|(?:voce\s+|vc\s+)?consegue\s+)?(?:me\s+)?"
RULES = [(kind, re.compile(rule)) for kind, rule in (
    ("forget", LEAD + r"(?:apag\w+|esquec\w+|limp\w+|delet\w+)\s+(?:(?:tudo\s+)?o que (?:voce|vc)\s+(?:viu|leu|olhou)|o diario da tela|o historico da tela)"),
    ("pause", LEAD + r"(?:para|pare|parar|pausa|pause|pausar|desliga|desligue)\s+(?:de\s+)?(?:olhar|ver|ler|a visao|a tela|de ver)|^nao\s+(?:olha|olhe|veja)\s+(?:a|minha)\s+tela"),
    ("resume", LEAD + r"(?:volta|volte|voltar|continua|continue|retoma|retome|liga|ligue)\s+(?:a\s+)?(?:a\s+)?(?:olhar|ver|ler|visao)"),
    ("summary", LEAD + r"(?:resume|resuma|resumir)(?:\s+(?:isso aqui|isso|aqui|(?:a|essa|esta|minha)\s+(?:tela|pagina)|(?:o|esse|este)\s+(?:texto|documento|site)))?[.!?]*$"),
    ("find", LEAD + r"(?:procura|procure|acha|ache|encontra|encontre|busca|busque)\s+(?P<query>.+?)\s+na\s+(?:minha\s+)?tela[.!?]?$"),
    ("recall", r"^(?:nek[ou][,:]?\s+)?o que (?:eu\s+)?(?:estava|tava)\s+(?:fazendo|vendo|olhando|lendo)\s+(?:as|a|por volta das?)\s+(?P<hour>\d{1,2})(?:[:h](?P<minute>\d{2}))?"),
    ("recall", r"^(?:nek[ou][,:]?\s+)?(?:quando|onde)\s+(?:eu\s+)?vi\s+(?P<query>.+?)[?.!]?$"),
    ("recall", r"^(?:nek[ou][,:]?\s+)?o que (?:eu\s+)?vi\s+(?:sobre|de|do|da)\s+(?P<query>.+?)[?.!]?$"),
    ("topics", r"^(?:nek[ou][,:]?\s+)?(?:o que voce aprendeu|o que aprendeu|sobre o que eu mais|quais (?:sao )?meus assuntos|no que eu mais)"),
    ("look", r"^(?:nek[ou][,:]?\s+)?(?:o que|oq|q)\s+(?:voce|vc|tu)\s+(?:esta|ta|tá)\s+vendo|^(?:nek[ou][,:]?\s+)?o que (?:tem|ha|aparece)\s+na\s+(?:minha\s+)?tela|"
             + LEAD + r"(?:le|leia|ler|olha|olhe|olhar|ve|ver|veja|descreve|descreva)\s+(?:a\s+|minha\s+)?tela|^(?:nek[ou][,:]?\s+)?(?:voce|vc)\s+(?:esta|ta)\s+vendo"),
)]

@dataclass
class ScreenCommand:
    kind: str
    query: str = ""
    hour: int = None
    minute: int = 0

def parse(text):
    clean = " ".join(text.split())
    folded = fold(clean)
    source = clean if len(clean) == len(folded) else folded
    for kind, rule in RULES:
        match = rule.search(folded)
        if not match:
            continue
        groups = match.groupdict()
        if groups.get("hour") and int(groups["hour"]) > 23:
            return None
        command = ScreenCommand(kind)
        if groups.get("query"):
            start, end = match.span("query")
            command.query = source[start:end].strip(" \"'“”.!?,;:")
        if groups.get("hour"):
            command.hour, command.minute = int(groups["hour"]), int(groups.get("minute") or 0)
        return command
    return None

REFERS_TO_SCREEN = re.compile(r"\b(tela|aqui|isso|esse erro|essa mensagem|esse texto|essa pagina|esse site|esse documento)\b")

def refers_to_screen(text):
    return bool(REFERS_TO_SCREEN.search(fold(text)))
