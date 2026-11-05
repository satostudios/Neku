"""Comandos de memória em português. Só leem o que o usuário digitou, nunca memórias nem o modelo."""
import re
from dataclasses import dataclass
from .store import expiry_date
from .text import fold

ANOTHER_DAY = r"\b(hoje|amanha|depois de amanha|esta semana|essa semana|nesta semana|semana que vem|proxima semana|segunda|terca|quarta|quinta|sexta|sabado|domingo)\b"
PREFIX = r"^(?:nek[ou][,:]?\s+)?(?:por favor[,:]?\s+)?(?:(?:voce\s+)?pode\s+)?"
SECRET = re.compile(r"\b(senhas?|password|passwd|cvv|token|pin|cpf|rg|cartao de credito|numero do cartao|chave pix|"
                    r"api key|apikey|frase de recuperacao)\b|\d{3}\.\d{3}\.\d{3}-\d{2}|\b\d{11,}\b")

RULES = [(kind, re.compile(rule)) for kind, rule in (
    ("forget_all", PREFIX + r"(?:esquec[ea]r?|apagu?e|apaga|apagar|delet[ea]r?|limp[ae]r?)\s+(?:tudo|todas? as? (?:suas? )?memorias?)\b"),
    ("query", r"^(?:nek[ou][,:]?\s+)?(?:o que (?:mais )?voce (?:sabe(?! fazer)|lembra|se lembra|guardou|anotou)\b|"
              r"lembra\b(?=.*\?$)|voce (?:ainda )?(?:se )?lembra\b|voce (?:ainda )?sabe (?:sobre|de|do|da|dos|das|meu|minha|quem sou|o que)\b|"
              r"quais (?:sao )?(?:as )?suas memorias|mostr[ae]r? (?:as )?(?:suas )?memorias)"),
    ("reminder", PREFIX + r"(?:me lembr[ae]r?(?: de)?|lembr[ae]-me(?: de)?|lembr[ae] de|lembr[ae]-se de)\s+(?!que\b)"),
    ("remember", PREFIX + r"(?:nao esquec[ea] (?:de )?que|lembr[ae](?:-se|r)?(?: de)? que|memoriz[ae]r?(?: que)?|"
                          r"guard[ae]r?(?: isso| ai)?(?::| que)|anot[ae]r?(?: isso| ai)?(?::| que)|"
                          r"salv[ae]r?(?: isso| ai)?(?::| que)|grav[ae]r?(?: isso| ai)?(?::| que))"),
    ("forget", PREFIX + r"(?:esquec[ea]r?(?!\s*,)|apagu?e da memoria|apaga da memoria|apagu?e a memoria|apaga a memoria|"
                        r"tir[ae]r? da memoria|remov[ae]r? da memoria)\b"),
    ("correct", PREFIX + r"(?:corrij[ae]|corrige|corrigir|atualiz[ae]r?)(?: a memoria| na memoria| sua memoria)?\s*:"),
    ("replace", PREFIX + r"(?:corrij[ae]|corrige|corrigir|troqu?e|troca|trocar)(?: na memoria)?\s+(?P<old>.+?)\s+(?:para|por)\s+(?P<new>.+)$"),
)]
NOISE_TARGET = re.compile(r"^(deixa pra la|deixa para la|nada|deixa)$")
FILLER = re.compile(r"^(?:que|sobre|de|do|da|o|a|os|as|mim|isso)\s+", re.I)

@dataclass
class Command:
    kind: str
    payload: str = ""
    old: str = ""
    new: str = ""

def _clean(text):
    return text.strip(" \t\"'“”.!,;:")

def _capitalize(text):
    return text[:1].upper() + text[1:]

def is_secret(text):
    return bool(SECRET.search(fold(text)))

def parse(text):
    clean = " ".join(text.split())
    folded = fold(clean)
    same_size = len(folded) == len(clean)
    source = clean if same_size else folded
    for kind, rule in RULES:
        match = rule.search(folded)
        if not match:
            continue
        rest = _clean(source[match.end():])
        if kind == "replace":
            start_old, end_old = match.span("old")
            start_new, end_new = match.span("new")
            old, new = _clean(source[start_old:end_old]), _clean(source[start_new:end_new])
            if old.lower() in ("de roupa", "ideias"):
                return None
            return Command("replace", old=old, new=new)
        if kind == "forget" and NOISE_TARGET.match(fold(rest)):
            return None
        return Command(kind, payload=rest)
    return None

def topic_of(payload):
    topic = _clean(payload.rstrip("?"))
    while FILLER.match(topic):
        topic = FILLER.sub("", topic, count=1)
    return topic

def categorize(text):
    """Devolve o arquivo da memória e, para anotações de curto prazo, a data em que deixam de valer."""
    folded = fold(text)
    if re.search(ANOTHER_DAY, folded):
        return "temporary.md", expiry_date()
    if re.search(r"\b(gosto|prefiro|adoro|amo|odeio|detesto|curto|favorit[oa]s?)\b", folded):
        return "preferences.md", None
    if re.search(r"\b(projeto|projetos|estou trabalhando|to trabalhando|estou desenvolvendo|estou fazendo)\b", folded):
        return "projects.md", None
    if re.search(r"^(eu )?(meu nome|me chamo|sou |moro|trabalho|tenho \d+ anos|nasci|minha |meu )", folded):
        return "user_profile.md", None
    return "important_memories.md", None

def statement(payload):
    return _capitalize(_clean(payload))
