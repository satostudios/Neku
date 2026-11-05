from . import commands
from .store import ChangedOnDisk, expiry_date
from .text import fold, tokens
from ..reply import Confirmation, Reply

MAX_LISTED = 6
MAX_CHANGED = 3

def bullet_list(entries):
    return "\n".join(f"• {entry.text}" for entry in entries)

class MemoryAssistant:
    def __init__(self, memory):
        self.memory = memory
        self.last_saved = None

    def handle(self, command):
        return getattr(self, "_" + command.kind)(command)

    def _secret_refused(self):
        return Reply("Prefiro não guardar isso: minhas memórias são arquivos de texto comum. "
                     "Senhas e documentos ficam melhores em um gerenciador de senhas.", mood="annoyed")

    def _save(self, text, name, until=None, origin="conversa"):
        result = self.memory.add(name, text, origin=origin, until=until)
        if result.status == "duplicate":
            return Reply(f"Eu já sei disso! Está guardado como: “{result.other.text}”.", mood="proud")
        if result.status == "conflict":
            return self._ask_conflict(result.other, text)
        self.last_saved = result.entry
        return Reply(f"Guardei em {name}: “{text}”.", mood="happy", effect="sparkle", xp=3)

    def _ask_conflict(self, old, text):
        def replace():
            return self._apply(lambda: self.memory.replace(old, text), f"Pronto, troquei por “{text}”.")

        return Reply(f"Hmm, isso muda o que eu sabia.\nAntes: “{old.text}”\nAgora: “{text}”", mood="confused",
                     confirm=Confirmation("Troco pela informação nova?", replace, self._kept))

    def _kept(self):
        return Reply("Tudo bem, deixei como estava.", mood="neutral")

    def _apply(self, change, message):
        try:
            change()
        except ChangedOnDisk:
            return Reply("Esse arquivo mudou enquanto a gente conversava, então não mexi em nada. Pode pedir de novo?",
                         mood="confused", effect="question")
        return Reply(message + " Guardei um backup da versão anterior.", mood="happy", xp=2)

    def _remember(self, command):
        text = commands.statement(command.payload)
        if not text:
            return Reply("O que você quer que eu guarde?", mood="curious")
        if commands.is_secret(text):
            return self._secret_refused()
        name, until = commands.categorize(text)
        return self._save(text, name, until)

    def _reminder(self, command):
        text = commands.statement(command.payload)
        if not text:
            return Reply("Lembrar do quê?", mood="curious")
        if commands.is_secret(text):
            return self._secret_refused()
        reply = self._save(text, "temporary.md", expiry_date())
        if reply.confirm is None and "Guardei" in reply.text:
            reply.text += " Sem um horário eu não consigo avisar sozinho; diga algo como “me lembra de X em 10 minutos”."
        return reply

    def _query(self, command):
        topic = commands.topic_of(command.payload)
        if not topic or fold(topic) in ("mim", "de mim", "sobre mim", "eu", "memorias", "tudo"):
            found = sorted(self.memory.personal_entries(), key=lambda e: e.day or "", reverse=True)
        else:
            found = self.memory.find(topic)
        if not found:
            return Reply("Ainda não guardei nada sobre isso. Se quiser, diga “lembre que…”.", mood="curious")
        extra = len(found) - MAX_LISTED
        text = "Isto é o que eu tenho guardado:\n" + bullet_list(found[:MAX_LISTED])
        return Reply(text + (f"\n…e mais {extra}." if extra > 0 else ""), mood="proud")

    def _target(self, topic):
        if fold(topic) in ("", "isso", "disso", "aquilo", "essa", "esse") and self.last_saved:
            return [self.last_saved]
        return self.memory.find(topic)

    def _forget(self, command):
        topic = commands.topic_of(command.payload)
        if not topic and not self.last_saved:
            return Reply("Esquecer o quê? Me diga sobre o que é.", mood="curious")
        found = self._target(topic)
        if not found:
            return Reply(f"Não achei nada sobre “{topic}”. Nada mudou.", mood="confused", effect="question")
        if len(found) > MAX_CHANGED:
            return Reply(f"Achei {len(found)} memórias. Me diga algo mais específico:\n"
                         + bullet_list(found[:MAX_CHANGED]), mood="confused")

        def remove():
            return self._apply(lambda: self.memory.remove_all(found), "Pronto, esqueci.")

        return Reply("Encontrei isto:\n" + bullet_list(found), mood="thinking",
                     confirm=Confirmation("Posso esquecer?", remove, self._kept))

    def _forget_all(self, command):
        return Reply("Não apago tudo de uma vez por conversa. Se quiser mesmo, abra Memórias no meu menu e edite por lá.",
                     mood="annoyed")

    def _correct(self, command):
        text = commands.statement(command.payload)
        if not text:
            return Reply("O que devo corrigir?", mood="curious")
        if commands.is_secret(text):
            return self._secret_refused()
        name, until = commands.categorize(text)
        return self._save(text, name, until)

    def _replace(self, command):
        if commands.is_secret(command.new):
            return self._secret_refused()
        wanted = fold(command.old)
        found = [entry for entry in self.memory.personal_entries() if wanted in fold(entry.text)]
        if not found:
            found = self.memory.find(command.old)
        if not found:
            return Reply(f"Não encontrei “{command.old}” nas minhas memórias. Nada mudou.", mood="confused", effect="question")
        if len(found) > MAX_CHANGED:
            return Reply(f"“{command.old}” aparece em {len(found)} memórias. Me diga algo mais específico.", mood="confused")
        changes = [(entry, _swap(entry.text, command.old, command.new)) for entry in found]

        def apply():
            return self._apply(lambda: self.memory.replace_all(changes), "Pronto, corrigi.")

        preview = "\n".join(f"• {entry.text} → {new}" for entry, new in changes)
        return Reply("Vou mudar assim:\n" + preview, mood="thinking",
                     confirm=Confirmation("Posso corrigir?", apply, self._kept))

def _swap(text, old, new):
    position = fold(text).find(fold(old))
    if position < 0 or len(fold(text)) != len(text):
        return new
    return text[:position] + new + text[position + len(old):]
