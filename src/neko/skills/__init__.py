"""Catálogo fechado de ações: nenhum pedido vira comando livre de terminal."""
import ctypes, logging, os, shutil, subprocess, threading, urllib.parse, webbrowser
from pathlib import Path
import psutil
from . import defender, files
from ..character import reaction
from ..memory.text import fold, tokens
from ..permissions import Permissions
from ..reply import Confirmation, Reply

log = logging.getLogger(__name__)

HELP = ("Sei fazer várias coisas no seu PC:\n"
        "• Abrir apps, pastas e sites, ou pesquisar na internet\n"
        "• Procurar arquivos pelo nome\n"
        "• Descompactar .zip e verificar vírus com o Defender\n"
        "• Organizar os Downloads (e desfazer)\n"
        "• Criar pastas e notas, mover, copiar, renomear e mandar para a Lixeira\n"
        "• Ver memória, disco e bateria, mudar o volume, bloquear a tela\n"
        "• Avisar você daqui a um tempo\n"
        "• Guardar, corrigir e esquecer o que você me pedir")
VK = {"up": 0xAF, "down": 0xAE, "mute": 0xAD}
SOFT = {"aumenta", "aumente", "sobe", "suba"}
LOUD_STEPS = 5

def size_difficulty(size):
    return 3 if size > 1024 ** 3 else 2 if size > 50 * 1024 ** 2 else 1

def tree_size(path):
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())

def done(text, difficulty=1, success=True, confirm=None):
    mood, effect = reaction(difficulty, success)
    return Reply(text, mood=mood, effect=effect, difficulty=difficulty, xp=5 * max(1, difficulty) if success else 0, confirm=confirm)

class Skills:
    def __init__(self, root, config, memory, notify=None):
        self.root, self.config, self.memory = Path(root), config, memory
        self.permissions = Permissions(config)
        self.notify = notify or (lambda reply: None)
        self.actions_dir = self.root / "data" / "actions"
        self.on_progress = lambda difficulty, text: None
        self.last_path = None
        self.apps = None

    def handle(self, request, on_progress=None):
        self.on_progress = on_progress or (lambda difficulty, text: None)
        try:
            return getattr(self, "_" + request.name)(**request.args)
        except OSError as error:
            log.warning("Falha em %s: %s", request.name, type(error).__name__)
            return done("Não consegui concluir isso. O Windows recusou a operação.", 2, False)

    def _gate(self, capability, question, action):
        if self.permissions.denied(capability):
            return Reply("Essa permissão está bloqueada nas minhas Configurações.", mood="annoyed")
        if self.permissions.needs_confirmation(capability):
            return Reply("", mood="curious", confirm=Confirmation(question, action, self._cancelled))
        return action()

    def _cancelled(self):
        return Reply("Tudo bem, não fiz nada.", mood="neutral")

    def _safe_roots(self):
        return [path for path in files.user_folders().values() if path.exists()]

    def _allowed(self, path):
        return files.is_inside(path, self._safe_roots()) and not files.is_inside(path, [self.root])

    def _resolve(self, target, ext=None, roots=None):
        """Devolve (caminho, erro): aceita o último citado, um nome ou o mais recente de um tipo."""
        name = fold(target).strip()
        if name in ("isso", "esse", "essa", "ele", "ela", "este", "esta", "aquele", "aquilo") and self.last_path:
            return self.last_path, None
        if not name or name.startswith(("ultimo", "ultima", "mais recente")):
            found = files.latest(files.known_folder("downloads"), ext or ".zip")
            return (found, None) if found else (None, Reply("Não achei nenhum arquivo assim nos Downloads.", mood="confused", effect="question"))
        found = files.search(roots or self._safe_roots(), target, ext, limit=4)
        exact = [path for path in found if fold(path.name) == name or fold(path.stem) == name]
        if len(exact) == 1 or len(found) == 1:
            return (exact or found)[0], None
        if not found:
            return None, Reply(f"Não encontrei “{target}” nas suas pastas.", mood="confused", effect="question")
        listing = "\n".join(f"• {path.name}" for path in found[:4])
        return None, Reply(f"Encontrei mais de um:\n{listing}\nQual deles? Pode dizer o nome completo.", mood="confused")

    def _help(self):
        return Reply(HELP, mood="proud")

    def _system(self, topic):
        memory = psutil.virtual_memory()
        ram = f"Memória: {memory.available / 1024 ** 3:.1f} GB livres de {memory.total / 1024 ** 3:.1f} GB."
        disk = psutil.disk_usage(Path.home().anchor)
        space = f"Disco: {disk.free / 1024 ** 3:.0f} GB livres de {disk.total / 1024 ** 3:.0f} GB."
        battery = psutil.sensors_battery()
        charge = "Sem bateria detectada." if battery is None else f"Bateria: {battery.percent:.0f}%" + (", carregando." if battery.power_plugged else ".")
        if "memoria" in topic or "ram" in topic:
            return done(ram)
        if "espaco" in topic or "disco" in topic:
            return done(space)
        if "bateria" in topic:
            return done(charge)
        return done(f"{ram}\n{space}\n{charge}")

    def _volume(self, action):
        down = action not in SOFT and not action.startswith(("mut", "sil", "tira", "desliga"))
        key = VK["mute"] if action.startswith(("mut", "sil", "tira", "desliga")) else VK["down"] if down else VK["up"]
        for _ in range(1 if key == VK["mute"] else LOUD_STEPS):
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)
        return done("Prontinho, ajustei o som.")

    def _lock(self):
        ctypes.windll.user32.LockWorkStation()
        return done("Tela bloqueada. Até já!")

    def _timer(self, seconds, text=""):
        message = text or "o aviso que você pediu"

        def fire():
            self.notify(Reply(f"Ei! Você pediu para eu avisar: {message}.", mood="excited", effect="exclaim"))

        timer = threading.Timer(seconds, fire)
        timer.daemon = True
        timer.start()
        when = f"{seconds // 3600} h" if seconds >= 3600 else f"{seconds // 60} min" if seconds >= 60 else f"{seconds} s"
        return done(f"Combinado, aviso em {when}. Se eu for fechado antes, o aviso se perde.")

    def _open_folder(self, folder):
        path = files.known_folder(folder)
        os.startfile(str(path))
        return done(f"Abri {files.FOLDER_NAMES[folder]}.")

    def _open_web(self, url, label):
        def action():
            webbrowser.open(url)
            return done(f"Abri {label} no navegador.")

        return self._gate("open_web", f"Posso abrir {label} no navegador?", action)

    def search_now(self, query):
        """Você já disse sim na oferta do agente: não pergunta de novo, mas respeita o bloqueio."""
        if self.permissions.denied("open_web"):
            return Reply("Essa permissão está bloqueada nas minhas Configurações.", mood="annoyed")
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}")
        return done("Abri a pesquisa no navegador.")

    def open_now(self, target):
        if self.permissions.denied("open_apps"):
            return Reply("Essa permissão está bloqueada nas minhas Configurações.", mood="annoyed")
        app = self._find_app(target)
        if app is None:
            return Reply(f"Não achei “{target}” no seu Menu Iniciar.", mood="confused", effect="question")
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app['AppID']}"])
        return done(f"Abri {app['Name']}.")

    def _web_search(self, query, site="google"):
        quoted = urllib.parse.quote_plus(query)
        url = (f"https://www.youtube.com/results?search_query={quoted}" if site == "youtube"
               else f"https://www.google.com/search?q={quoted}")
        return self._open_web(url, f"a pesquisa “{query}”")

    def _find_app(self, target):
        if self.apps is None:
            self.apps = files.start_apps()
        wanted, words = fold(target), tokens(target)
        exact = [app for app in self.apps if fold(app.get("Name", "")) == wanted]
        return (exact or [app for app in self.apps if wanted in fold(app.get("Name", "")) or (words and words <= tokens(app.get("Name", "")))] or [None])[0]

    def _open_app(self, target):
        from .parser import SITES
        app = self._find_app(target)
        if app is None:
            site = SITES.get(fold(target))
            if site:
                return self._open_web(site, target)
            return Reply(f"Não achei “{target}” no seu Menu Iniciar.", mood="confused", effect="question")

        def action():
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app['AppID']}"])
            return done(f"Abri {app['Name']}.")

        return self._gate("open_apps", f"Posso abrir {app['Name']}?", action)

    def _find(self, query="", ext=None, folder=None):
        roots = [files.known_folder(folder)] if folder else self._safe_roots()

        def action():
            found = files.search(roots, query, ext)
            if not found:
                return done("Procurei e não encontrei nada com esse nome.", 2, False)
            self.last_path = found[0]
            listing = "\n".join(f"• {path.name}" for path in found[:6])
            extra = f"\n…e mais {len(found) - 6}." if len(found) > 6 else ""
            return done(f"Encontrei:\n{listing}{extra}", 2)

        return self._gate("read_files", "Posso procurar pelos nomes de arquivo nas suas pastas? Não abro o conteúdo deles.", action)

    def _scan(self, target):
        path, problem = self._resolve(target)
        if problem:
            return problem
        self.last_path = path
        difficulty = size_difficulty(tree_size(path))
        self.on_progress(difficulty, f"Verificando {path.name} com o Defender…")
        return self._scan_reply(path, defender.scan(path), difficulty)

    def _scan_reply(self, path, result, difficulty):
        if result.threat:
            return done(f"⚠ O Defender encontrou uma ameaça em {path.name}. Não abra esse arquivo!", 3, False)
        if result.clean:
            return done(f"O Defender não encontrou ameaças em {path.name}. Isso ajuda muito, mas nenhuma verificação é garantia total.", difficulty)
        return done("Não consegui usar o Defender agora, então não sei dizer se é seguro.", 2, False)

    def _extract(self, target=""):
        path, problem = self._resolve(target, ".zip")
        if problem:
            return problem
        if path.suffix.lower() != ".zip":
            return Reply(f"Por enquanto só descompacto .zip, e {path.name} não é um.", mood="confused")
        if self.permissions.denied("write_files"):
            return Reply("Essa permissão está bloqueada nas minhas Configurações.", mood="annoyed")
        return Reply("", mood="curious", confirm=Confirmation(
            f"Posso verificar e descompactar {path.name}?", lambda: self.process_zip(path), self._cancelled))

    def process_zip(self, path):
        """Verifica, extrai para uma pasta nova, verifica de novo e dá um parecer. Nunca abre nada."""
        difficulty = size_difficulty(path.stat().st_size)
        self.on_progress(difficulty, f"Verificando {path.name} antes de abrir…")
        first = defender.scan(path)
        if first.threat:
            return self._scan_reply(path, first, 3)
        if not first.clean:
            return done(f"Não extraí {path.name}: o Defender não está disponível para verificar antes.", 2, False)
        destination = files.unique_path(path.with_suffix(""))
        try:
            count = files.safe_extract(path, destination)
        except files.UnsafeArchive as error:
            return done(f"Não extraí {path.name} porque {error}.", 3, False)
        self.on_progress(difficulty, f"Extraí {count} arquivo(s). Conferindo o conteúdo…")
        second = defender.scan(destination)
        if second.threat:
            return done(f"⚠ O Defender encontrou ameaça dentro de {path.name}. Não abra a pasta {destination.name}!", 3, False)
        self.last_path = destination
        verdict = self._verdict(destination, second)

        def open_folder():
            os.startfile(str(destination))
            return done(f"Abri {destination.name}.")

        return done(f"Descompactei {path.name} em {destination.name}. {verdict}", difficulty,
                    confirm=Confirmation("Quer abrir a pasta?", open_folder, lambda: Reply("Certo, fica aí guardada.", mood="neutral"),
                                         "Abrir", "Agora não"))

    def _verdict(self, folder, scan_result):
        report = files.inspect(folder)
        checked = "O Defender não achou ameaças." if scan_result.clean else "Não consegui verificar o conteúdo com o Defender."
        if report["disguised"]:
            return f"{checked} ⚠ Mas {report['disguised'][0]} parece disfarçado de outro tipo de arquivo. Eu não abriria."
        if report["risky"]:
            count = len(report["risky"])
            return f"{checked} Tem {count} arquivo(s) que executam programas, como {report['risky'][0]}. Abra só se confiar em quem enviou."
        return f"{checked} São {report['total']} arquivo(s) comuns, nada que execute programas. Parece tranquilo."

    def _organize(self, folder):
        if folder != "downloads":
            return Reply("Por enquanto só organizo a pasta Downloads.", mood="confused")
        path = files.known_folder("downloads")
        plan = files.group_by_category(path)
        if not plan:
            return Reply("Seus Downloads já estão organizados!", mood="proud", effect="sparkle")
        counts = {}
        for _, category in plan:
            counts[category] = counts.get(category, 0) + 1
        summary = "\n".join(f"• {category}: {count}" for category, count in sorted(counts.items()))

        def action():
            difficulty = 3 if len(plan) > 200 else 2
            self.on_progress(difficulty, "")
            moved = files.apply_organization(path, plan, self.actions_dir)
            return done(f"Organizei {moved} arquivo(s). Se não gostar, diga “desfaz a organização”.", difficulty)

        return self._write_gate(f"Vou mover {len(plan)} arquivo(s) para subpastas:\n{summary}", "Posso organizar?", action)

    def _write_gate(self, text, question, action):
        if self.permissions.denied("write_files"):
            return Reply("Essa permissão está bloqueada nas minhas Configurações.", mood="annoyed")
        return Reply(text, mood="thinking", confirm=Confirmation(question, action, self._cancelled))

    def _undo(self):
        restored = files.undo_organization(self.actions_dir)
        if restored is None:
            return Reply("Não tenho nenhuma organização para desfazer.", mood="confused")
        return done(f"Desfeito! Devolvi {restored} arquivo(s) para o lugar.", 2)

    def _create_folder(self, name, folder="desktop"):
        clean = files.valid_name(name)
        if not clean:
            return Reply("Esse nome não serve para uma pasta no Windows.", mood="confused")
        target = files.unique_path(files.known_folder(folder) / clean)

        def action():
            target.mkdir(parents=True)
            self.last_path = target
            return done(f"Criei a pasta {target.name}.")

        return self._write_gate(f"Vou criar {target.name} em {files.FOLDER_NAMES[folder]}.", "Posso criar?", action)

    def _create_note(self, name, content):
        clean = files.valid_name(name)
        if not clean:
            return Reply("Esse nome não serve para um arquivo no Windows.", mood="confused")
        if not Path(clean).suffix:
            clean += ".txt"
        target = files.unique_path(files.known_folder("documents") / clean)

        def action():
            target.write_text(content, encoding="utf-8")
            self.last_path = target
            return done(f"Criei {target.name} em Documentos.")

        return self._write_gate(f"Vou criar {target.name} em Documentos.", "Posso criar?", action)

    def _transfer(self, source, folder, verb, operation):
        path, problem = self._resolve(source)
        if problem:
            return problem
        if not self._allowed(path):
            return Reply("Só mexo em arquivos dentro das suas pastas pessoais.", mood="annoyed")
        target = files.unique_path(files.known_folder(folder) / path.name)

        def action():
            operation(str(path), str(target))
            self.last_path = target
            return done(f"Pronto, {path.name} {verb} {files.FOLDER_NAMES[folder]}.", size_difficulty(tree_size(target)))

        return self._write_gate(f"{path.name} {verb} {files.FOLDER_NAMES[folder]}.", "Confirma?", action)

    def _move(self, source, folder):
        return self._transfer(source, folder, "vai para", shutil.move)

    def _copy(self, source, folder):
        return self._transfer(source, folder, "será copiado para", shutil.copy2)

    def _rename(self, source, name):
        path, problem = self._resolve(source)
        if problem:
            return problem
        clean = files.valid_name(name)
        if not clean:
            return Reply("Esse nome não serve no Windows.", mood="confused")
        if not self._allowed(path):
            return Reply("Só mexo em arquivos dentro das suas pastas pessoais.", mood="annoyed")
        if not Path(clean).suffix:
            clean += path.suffix
        target = files.unique_path(path.with_name(clean))

        def action():
            path.rename(target)
            self.last_path = target
            return done(f"Renomeei para {target.name}.")

        return self._write_gate(f"{path.name} → {target.name}", "Posso renomear?", action)

    def _trash(self, target):
        path, problem = self._resolve(target)
        if problem:
            return problem
        if not self._allowed(path):
            return Reply("Só mexo em arquivos dentro das suas pastas pessoais.", mood="annoyed")

        def action():
            files.send_to_trash(path)
            return done(f"{path.name} está na Lixeira. Dá para recuperar por lá.")

        return self._write_gate(f"Vou mandar {path.name} para a Lixeira.", "Confirma?", action)
