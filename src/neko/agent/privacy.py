"""O que o Neku se recusa a ler: decide antes do OCR e limpa o texto antes de guardar."""
import re
from ..memory.text import fold

PRIVATE_APPS = frozenset({"keepass.exe", "keepassxc.exe", "bitwarden.exe", "1password.exe", "lastpass.exe", "dashlane.exe",
                          "credentialuibroker.exe", "consent.exe", "logonui.exe", "lockapp.exe", "securityhealthsystray.exe"})
PRIVATE_TITLE = re.compile(r"inprivate|anonim[oa]|incognito|private browsing|navegacao privada|\bsenhas?\b|\bpassword\b|"
                           r"internet banking|\bbanco\b|\bbank\b|nubank|itau|bradesco|santander|banco do brasil|caixa economica|"
                           r"\bpicpay\b|mercado pago|paypal|gerenciador de senhas|cofre de senhas")
REDACTIONS = (
    (re.compile(r"(?i)\b(senha|password|passwd|pwd|token|api[_ -]?key|secret|cvv|pin)\b\s*[:=]\s*\S+"), r"\1: [oculto]"),
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[cpf oculto]"),
    (re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"), "[cnpj oculto]"),
    (re.compile(r"\b(?:\d[ .-]?){13,19}\b"), "[número oculto]"),
    (re.compile(r"\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}\b"), "[token oculto]"),
    (re.compile(r"\b(?:sk|pk|ghp|gho|xox[bp]|AKIA)[-_]?[A-Za-z0-9_-]{16,}\b"), "[chave oculta]"),
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "[código oculto]"),
)

def is_private(app, title, ignored_apps=(), ignored_titles=()):
    name = (app or "").lower()
    if name in PRIVATE_APPS or name in {str(item).lower() for item in ignored_apps}:
        return True
    folded = fold(title or "")
    return bool(PRIVATE_TITLE.search(folded)) or any(fold(str(item)) in folded for item in ignored_titles if item)

def redact(text):
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text
