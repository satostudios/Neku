"""Entende pedidos de ação em português. Só lê o que o usuário digitou; nunca arquivos nem o modelo."""
import re
from dataclasses import dataclass, field
from ..memory.text import fold

@dataclass
class Request:
    name: str
    args: dict = field(default_factory=dict)

FOLDERS = {"downloads": "downloads", "download": "downloads", "baixados": "downloads", "transferencias": "downloads",
           "documentos": "documents", "imagens": "pictures", "fotos": "pictures", "area de trabalho": "desktop",
           "desktop": "desktop", "musicas": "music", "videos": "videos"}
SITES = {"youtube": "https://www.youtube.com", "google": "https://www.google.com", "gmail": "https://mail.google.com",
         "github": "https://github.com", "whatsapp": "https://web.whatsapp.com", "netflix": "https://www.netflix.com",
         "instagram": "https://www.instagram.com", "claude": "https://claude.ai", "spotify": "https://open.spotify.com"}
FILE_WORDS = {"pdf": ".pdf", "pdfs": ".pdf", "zip": ".zip", "zips": ".zip", "foto": "imagem", "fotos": "imagem",
              "imagem": "imagem", "imagens": "imagem", "planilha": ".xlsx", "planilhas": ".xlsx", "documento": ".docx",
              "documentos": ".docx", "video": "video", "videos": "video"}
NUMBERS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "cinco": 5, "dez": 10, "quinze": 15, "vinte": 20,
           "trinta": 30, "meia": 30}

LEAD = r"^(?:nek[ou][,:]?\s+)?(?:por favor[,:]?\s+)?(?:(?:voce\s+|vc\s+)?pode\s+|(?:voce\s+|vc\s+)?consegue\s+)?(?:me\s+)?"
FOLDER_RE = "|".join(sorted(map(re.escape, FOLDERS), key=len, reverse=True))
DURATION = r"(?P<n>\d+|um|uma|dois|duas|tres|cinco|dez|quinze|vinte|trinta|meia)\s*(?P<unit>minutos?|min|horas?|h|segundos?|seg)\b"
OPEN = r"(?:abre|abra|abrir)"
ARTICLE = r"(?:(?:o|a|os|as|esse|essa|este|esta|aquele|aquela|meu|minha|meus|minhas)\s+)?"
TARGET_WORD = r"(?:(?:arquivo|pasta|documento)\s+)?"

PATTERNS = [
    ("help", rf"{LEAD}(?:o que|oq|q)\s+(?:voce|vc)\s+(?:sabe|consegue|pode)\s+fazer|{LEAD}(?:quais|que)\s+(?:sao\s+)?(?:suas|as)\s+(?:habilidades|acoes|funcoes)"),
    ("undo", rf"{LEAD}desfa(?:ca|z|zer)\s+(?:a\s+)?(?:ultima\s+)?organiza"),
    ("system", rf"(?P<topic>quanta\s+(?:memoria|ram)|quanto\s+de\s+(?:memoria|ram)|uso\s+de\s+(?:memoria|ram)|espaco\s+(?:livre|em\s+disco|no\s+disco)|quanto\s+de\s+(?:espaco|disco)|bateria|como\s+(?:esta|ta)\s+(?:o|meu)\s+(?:pc|computador|notebook))"),
    ("volume", rf"{LEAD}(?P<action>aumenta|aumente|sobe|suba|abaixa|abaixe|diminui|diminua|baixa|baixe|muta|mute|silencia|silencie)\s+(?:o\s+)?(?:volume|som)\b|{LEAD}(?P<action2>tira|desliga)\s+o\s+som\b"),
    ("lock", rf"{LEAD}(?:bloqueia|bloqueie|trava|trave)\s+(?:o\s+|a\s+)?(?:pc|computador|notebook|tela)[.!]?$"),
    ("organize", rf"{LEAD}(?:organiza|organize|organizar|arruma|arrume|arrumar)\s+(?:a\s+|minha\s+|meus?\s+|os\s+)?(?:pasta\s+)?(?:de\s+|dos\s+)?(?P<folder>{FOLDER_RE})\b"),
    ("extract", rf"{LEAD}(?:descompacta|descompacte|descompactar|extrai|extraia|extrair|unzipa|unzip)\b\s*{ARTICLE}{TARGET_WORD}(?P<target>.*)$"),
    ("scan", rf"{LEAD}(?:verifica|verifique|verificar|checa|cheque|analisa|analise|ve|veja)\s+(?:se\s+)?{ARTICLE}{TARGET_WORD}(?P<target>.+?)\s+(?:tem\s+virus|tem\s+ameaca|e\s+seguro|esta\s+seguro|ta\s+seguro)[?.!]?$"),
    ("scan", rf"{LEAD}(?:escaneia|escaneie|escanear)\s+{ARTICLE}{TARGET_WORD}(?P<target>.+)$"),
    ("scan", rf"{LEAD}(?:passa|passe|passar)\s+o\s+antivirus\s+(?:em|no|na|nesse|nessa)\s+{TARGET_WORD}(?P<target>.+)$"),
    ("create_folder", rf"{LEAD}(?:cria|crie|criar|faz|faca|fazer)\s+(?:uma\s+)?(?:nova\s+)?pasta\s+(?:chamada\s+|com\s+o\s+nome\s+|de\s+nome\s+)?(?P<name>.+?)(?:\s+(?:na|no|nas|nos|em|dentro\s+de)\s+(?:a\s+|meus?\s+|minhas?\s+)?(?P<folder>{FOLDER_RE}))?[.!]?$"),
    ("create_note", rf"{LEAD}(?:cria|crie|criar|escreve|escreva)\s+(?:um\s+|uma\s+)?(?:arquivo|nota)(?:\s+de\s+texto)?\s+(?:chamad[oa]\s+|com\s+o\s+nome\s+)?(?P<name>.+?)\s+(?:com\s+o\s+texto|com|dizendo|escrito)\s+(?P<content>.+)$"),
    ("rename", rf"{LEAD}(?:renomeia|renomeie|renomear|muda\s+o\s+nome\s+de|mude\s+o\s+nome\s+de)\s+{ARTICLE}{TARGET_WORD}(?P<source>.+?)\s+para\s+(?P<name>.+)$"),
    ("move", rf"{LEAD}(?:move|mova|mover|manda|mande|mandar|leva|leve)\s+{ARTICLE}{TARGET_WORD}(?P<source>.+?)\s+(?:para|pra)\s+(?:a\s+|o\s+|pasta\s+|meus?\s+|minhas?\s+)*(?P<folder>{FOLDER_RE})[.!]?$"),
    ("copy", rf"{LEAD}(?:copia|copie|copiar)\s+{ARTICLE}{TARGET_WORD}(?P<source>.+?)\s+(?:para|pra)\s+(?:a\s+|o\s+|pasta\s+|meus?\s+|minhas?\s+)*(?P<folder>{FOLDER_RE})[.!]?$"),
    ("trash", rf"{LEAD}(?:manda|mande|joga|jogue|envia|envie|coloca|coloque)\s+{ARTICLE}{TARGET_WORD}(?P<target>.+?)\s+(?:para|pra|na)\s+(?:a\s+)?lixeira[.!]?$"),
    ("trash", rf"{LEAD}(?:apaga|apague|apagar|deleta|delete|deletar|exclui|exclua|excluir|remove|remova|remover)\s+{ARTICLE}(?:arquivo|pasta)\s+(?P<target>.+?)[.!]?$"),
    ("trash", rf"{LEAD}(?:apaga|apague|apagar|deleta|delete|deletar|exclui|exclua|excluir)\s+{ARTICLE}(?P<target>\S+\.[a-z0-9]{{2,5}})[.!]?$"),
    ("open_folder", rf"{LEAD}(?:{OPEN}|mostra|mostre)\s+(?:a\s+|o\s+|minha\s+|meu\s+|meus\s+|minhas\s+|os\s+|as\s+)?(?:pasta\s+)?(?:de\s+|dos\s+|das\s+)?(?P<folder>{FOLDER_RE})[.!]?$"),
    ("find", rf"{LEAD}(?:procura|procure|procurar|acha|ache|achar|encontra|encontre|encontrar|busca|busque|buscar|localiza|localize)\s+(?:(?:o|a|os|as|meu|minha|meus|minhas|um|uma)\s+)?(?P<kind>arquivos?|pdfs?|zips?|fotos?|imagens?|planilhas?|documentos?|videos?)\b(?:\s+(?:de|do|da|chamad[oa]s?|com\s+o\s+nome|sobre))?\s*(?P<query>.*?)(?:\s+(?:em|na|no|nos)\s+(?:a\s+|meus?\s+|minhas?\s+)?(?P<folder>{FOLDER_RE}))?[.!?]?$"),
    ("web_search", rf"{LEAD}(?:pesquisa|pesquise|pesquisar|procura|procure|busca|busque|googla|googlar)\s+(?:(?:no|na)\s+(?P<site>google|youtube|internet|web)\s+)?(?:por\s+|sobre\s+)?(?P<query>.+?)(?:\s+(?:no|na)\s+(?P<site2>google|youtube|internet|web))?[.!?]?$"),
    ("open_app", rf"{LEAD}(?:{OPEN}|inicia|inicie|iniciar|executa|execute|executar|roda|rode|rodar|entra\s+no|entre\s+no|entra\s+na|entre\s+na|vai\s+no|vai\s+na)\s+(?:o\s+|a\s+|meu\s+|minha\s+)?(?P<target>.+?)[.!]?$"),
]
PATTERNS = [(name, re.compile(rule)) for name, rule in PATTERNS]
TIMERS = [re.compile(rule) for rule in (
    rf"{LEAD}(?:lembr[ae]r?|avis[ae]r?)(?:-me)?(?:\s+(?:de|que|para|pra))?\s+(?P<what>.+?)\s+(?:daqui\s+a|daqui|em)\s+{DURATION}[.!]?$",
    rf"{LEAD}(?:lembr[ae]r?|avis[ae]r?)(?:-me)?\s+(?:daqui\s+a|daqui|em)\s+{DURATION}\s*(?:de|que|para|pra)?\s*(?P<what>.*)$",
)]

def _seconds(amount, unit):
    value = NUMBERS.get(amount) or int(amount)
    if amount == "meia":
        return 1800
    if unit.startswith("h"):
        return value * 3600
    return value * 60 if unit.startswith("min") else value

def _strip(text):
    return (text or "").strip(" \t\"'“”.!?,;:")

def parse(text):
    clean = " ".join(text.split())
    folded = fold(clean)
    source = clean if len(clean) == len(folded) else folded
    for rule in TIMERS:
        match = rule.search(folded)
        if match:
            start, end = match.span("what")
            return Request("timer", {"seconds": _seconds(match["n"], match["unit"]), "text": _strip(source[start:end])})
    for name, rule in PATTERNS:
        match = rule.search(folded)
        if not match:
            continue
        args = {}
        for key, value in match.groupdict().items():
            if value is None:
                continue
            start, end = match.span(key)
            args[key] = _strip(source[start:end])
        return _finish(name, args)
    return None

def _finish(name, args):
    if "folder" in args:
        args["folder"] = FOLDERS.get(fold(args["folder"]), args["folder"])
    if name == "volume":
        args["action"] = fold(args.get("action") or args.get("action2", "tira"))
        args.pop("action2", None)
    if name == "system":
        args["topic"] = fold(args["topic"])
    if name == "find":
        args["ext"] = FILE_WORDS.get(fold(args.pop("kind")))
        match = re.search(r"\.[a-z0-9]{2,5}\b", args.get("query", ""))
        if match:
            args["ext"] = match[0]
            args["query"] = _strip(args["query"].replace(match[0], ""))
        elif fold(args.get("query", "")) in FILE_WORDS:
            args["ext"] = FILE_WORDS[fold(args["query"])]
            args["query"] = ""
    if name == "web_search":
        site = fold(args.pop("site", "") or args.pop("site2", ""))
        args.pop("site2", None)
        args["site"] = "youtube" if site == "youtube" else "google"
    if name == "open_app" and fold(args.get("target", "")) in ("isso", "esse", "essa", "ele", "ela", ""):
        return None
    return Request(name, args)
