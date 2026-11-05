import re, unicodedata

STOPWORDS = frozenset(
    "a o as os um uma uns umas de do da dos das em no na nos nas e ou que com para pra por se eu tu ele ela "
    "meu minha meus minhas seu sua seus suas voce nao sim mas mais muito como ao aos sobre isso esse essa este "
    "esta aquilo la aqui ja foi ser ter tem sou era me te lhe".split())

def fold(text):
    """Minúsculas e sem acentos, preservando o tamanho do texto sempre que possível."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))

def tokens(text):
    return {word[:5] for word in re.findall(r"[a-z0-9]+", fold(text)) if word not in STOPWORDS and len(word) > 1}
