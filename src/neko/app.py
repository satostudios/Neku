"""O Neku: o motor Pestinha como corpo e cérebro, com o agente, a conversa e a visão por cima."""
import logging, sys, threading, time
from pathlib import Path
from PySide6.QtCore import QFileSystemWatcher, QLockFile, QRect, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox
from pestinha import config as engine_config
from pestinha.app import PestinhaApp
from pestinha.body.pet import PetWindow, cursor_pos
from pestinha.paths import Paths
from pestinha.settings_store import SettingsStore
from pestinha.ui.ui import SettingsDialog as BodySettings
from . import __version__, autostart, brain
from .agent import capture
from .agent import journal as screen_journal
from .agent.agent import ScreenAgent
from .agent.vision import VisionWorker
from .character import Evolution
from .chat import ChatController
from .companion import Companion
from .config import Config
from .habits import Habits
from .hotkey import GlobalHotkey
from .memory import Memory
from .memory_dialog import MemoryDialog
from .observer import Observer
from .reply import Confirmation, Reply
from .runtime import ModelRuntime
from .settings_dialog import SettingsDialog
from .skills import Skills, files
from .sprite import ALTURA, LADO_JANELA, LARGURA, UNIDADE, Sprite

log = logging.getLogger(__name__)

AGENT_THINK_MS = 1000
DOWNLOAD_CHECK_MS = 4000
RUNTIME_CHECK_MS = 60000
SAVE_LEARNED_MS = 60000
FIRST_OFFER_SECONDS = 60.0
FOLLOW_SECONDS = 15.0
FOLLOW_GAP = 70
EDGE_MARGIN = 40
VISION_IDLE_LIMIT = 90.0
FACE_SECONDS = 3.5
FACE_PRIORITY = 25
ENGINE_DEFAULTS = {"pet": "neko", "configurado": True, "pousar_janelas": False, "bolinha": False, "fogos": False,
                   "protesto": False, "travessuras": False}
MOODS = {"neutral": "observando", "happy": "feliz", "proud": "contente", "excited": "feliz", "curious": "curioso",
         "confused": "curioso", "thinking": "curioso", "working": "observando", "annoyed": "bravo", "sad": "triste",
         "surprised": "assustado"}
WELCOME = ("Oi! Agora sou o seu agente, aqui em cima da barra de tarefas. ✦ Aperte Ctrl+Alt+N para falar comigo "
           "de qualquer lugar.\n\nPara aprender com você, preciso da sua autorização para:\n"
           "• ler o texto de tudo que aparece na tela, inclusive mensagens e documentos, e guardar esse texto por 7 dias\n"
           "• acompanhar os nomes dos arquivos em Downloads\n\n"
           "Tudo fica neste computador e nenhuma imagem é guardada. Escondo as janelas de senha e de banco que "
           "reconheço, e o led verde mostra quando estou olhando.")

class Presence:
    """O que a conversa enxerga do corpo. Separado do app, cujo `activity` é a atividade do usuário."""
    def __init__(self, app):
        self.app = app

    def rect(self):
        body = self.app.pet.body
        half_w, half_h = int(body.half_w), int(body.half_h)
        return QRect(int(body.x) - half_w, int(body.y) - half_h, half_w * 2, half_h * 2)

    def mood(self, name, seconds=FACE_SECONDS):
        emotion = MOODS.get(name)
        if emotion:
            self.app.emotion.force(emotion, seconds, time.monotonic(), FACE_PRIORITY)

    def activity(self, name):
        self.app.sprite.atividade = name

def sync_autostart(root, config):
    try:
        autostart.sync(root, config.get("start_with_windows",False))
        return True
    except OSError:
        log.exception("Não foi possível ajustar a inicialização com o Windows")
        return False

class NekoApp(PestinhaApp):
    QUADRO_MS = 33

    def __init__(self, store, paths, root):
        brain.extend()
        self.root = Path(root)
        self.settings_neko = Config(self.root)
        self.sprite = Sprite(unidade=max(1, round(UNIDADE * self.settings_neko.get("scale", 1.0))))
        self.vision = None
        super().__init__(store, paths)
        self.tray.icon.setIcon(QIcon(QPixmap.fromImage(self.sprite.imagem("feliz"))))
        self.tray.icon.setToolTip("Neku")
        self.sprite.corpo = self.pet.body
        if not self.settings_neko.get("notebook_visible", False) and not self.mesa.escondido:
            self.mesa.alternar_notebook()
        self._typed_at = -FOLLOW_SECONDS
        self._build_agent()
        self._build_interface()
        self._start_agent()

    # ---------- montagem ----------

    def _criar_pet(self, x, y):
        unidade = self.sprite.unidade
        corpo = (LARGURA * unidade, ALTURA * unidade)
        left, top, right, bottom = self.bounds()
        saved = self.settings_neko.get("window_pos", [])
        x = saved[0] if len(saved) == 2 and left <= saved[0] <= right else right - 160
        return PetWindow(x, bottom - corpo[1] / 2, self.pet_state, corpo=corpo, lado=max(LADO_JANELA, corpo[1] * 2), pintor=self.sprite)

    def _build_agent(self):
        settings = self.settings_neko
        self.neko_memory = Memory(self.root)
        self.neko_observer = Observer(self.neko_memory, settings)
        self.evolution = Evolution(self.root)
        self.runtime = ModelRuntime(self.root, settings)
        self.skills = Skills(self.root, settings, self.neko_memory, self.notify)
        self.habits = Habits(self.neko_memory, settings, self.skills, self.notify)
        self.companion = Companion(self.neko_memory, settings, self.runtime, self.skills)
        self.presence = Presence(self)
        self.chat = ChatController(self.companion, self.presence, self.evolution)
        vision = settings.get("vision", {})
        self.journal = screen_journal.ScreenJournal(self.root / "data" / "tela", vision.get("retention_days", 7))
        self.journal.purge()
        self.agent = ScreenAgent(self.root / "data" / "tela_aprendizado", self.journal, self.skills, self.neko_memory,
                                 self.notify, settings, self.companion.llm)
        self.companion.agent = self.agent
        self.agent.next_offer = time.monotonic() + FIRST_OFFER_SECONDS
        self.agent.on_offer_expired = self.chat.expire_offer

    def _build_interface(self):
        self.memories = None
        menu = self.tray.menu
        first = menu.actions()[0]
        for text, slot in (("Conversar (Ctrl+Alt+N)", self.chat.open), ("Memórias", self.open_memory),
                           ("Configurações do agente", self.open_agent_settings)):
            action = menu.addAction(text, slot)
            menu.removeAction(action)
            menu.insertAction(first, action)
        menu.insertSeparator(first)
        self.tray.actions["settings"].setText("Configurações do corpo")
        self.hotkey_chat = GlobalHotkey(QApplication.instance(), self.chat.open)

    def _start_agent(self):
        self.watcher = QFileSystemWatcher()
        self.pulse = self._timer(DOWNLOAD_CHECK_MS, self._check_downloads)
        self.pulse.stop()
        self.watcher.directoryChanged.connect(lambda _: QTimer.singleShot(1200, self._check_downloads))
        self.habits.start()
        self._refresh_downloads()
        self._last_agent_tick = time.monotonic()
        self._timer(AGENT_THINK_MS, self._agent_tick)
        self._timer(RUNTIME_CHECK_MS, self.runtime.stop_if_idle)
        self._timer(SAVE_LEARNED_MS, self.agent.save)
        self._update_vision()
        if not self.settings_neko.get("agent_onboarded", False):
            QTimer.singleShot(900, self._welcome)

    def _welcome(self):
        def finish(allowed):
            settings = self.settings_neko
            settings.data["agent_onboarded"] = True
            settings.data["watch_downloads"] = allowed
            settings.data["vision"]["enabled"] = allowed
            settings.save()
            QTimer.singleShot(0, self._refresh_all)
            text = "Combinado! Led verde aceso: estou olhando." if allowed else "Sem problemas. Dá para ligar nas Configurações."
            return Reply(text, mood="happy" if allowed else "neutral")

        self.notify(Reply(WELCOME, mood="excited", confirm=Confirmation("Posso?", lambda: finish(True), lambda: finish(False), "Pode", "Agora não")))

    def notify(self, reply):
        self.chat.notice_ready.emit(reply)

    # ---------- encaixes no motor ----------

    def sinais_extras(self):
        return self.agent.signals() if hasattr(self, "agent") else {}

    def recompensa_extra(self):
        return self.agent.pop_reward() if hasattr(self, "agent") else 0.0

    def frame(self):
        super().frame()
        if not hasattr(self, "chat") or not self.pet.isVisible():
            return
        now = time.monotonic()
        if self.keyboard_active:
            self._typed_at = now
        body = self.pet.body
        talking = self.chat.busy or self.chat.bubble.isVisible()
        if talking:
            self.behavior.seguir_x = body.x
            self.chat.follow()
        elif self.settings_neko.get("follow_mouse", True) and now - self._typed_at < FOLLOW_SECONDS:
            self.behavior.seguir_x = self._follow_x(cursor_pos()[0])
        else:
            self.behavior.seguir_x = None

    def _follow_x(self, cursor_x):
        left, _top, right, _bottom = self.bounds()
        x = cursor_x + FOLLOW_GAP if cursor_x + FOLLOW_GAP < right - EDGE_MARGIN else cursor_x - FOLLOW_GAP
        return max(left + EDGE_MARGIN, min(right - EDGE_MARGIN, x))

    # ---------- agente ----------

    def _vision_should_pause(self):
        return (self._congelado() or self.hidden or self.agent.paused or self.asleep
                or self.idle_seconds > VISION_IDLE_LIMIT or self.activity == "GAMING"
                or not self.settings_neko.get("vision", {}).get("enabled", False))

    def _own_windows(self):
        rects = []
        for widget in (self.pet, self.chat.bubble):
            if widget.isVisible():
                info = capture.window_info(int(widget.winId()))
                if info:
                    rects.append(info[2])
        return rects

    def _update_vision(self):
        enabled = self.settings_neko.get("vision", {}).get("enabled", False)
        if enabled and self.vision is None:
            self.snapshot_bridge = self.chat
            self.vision = VisionWorker(self.settings_neko, self._snapshot_seen, self._vision_should_pause, self._own_windows)
            self.vision.start()
        elif not enabled and self.vision is not None:
            self.vision.stop()
            self.vision = None
        self._update_indicator()

    def _snapshot_seen(self, snapshot):
        QTimer.singleShot(0, self.chat, lambda: self.agent.observe(snapshot))

    def _update_indicator(self):
        if not self.settings_neko.get("vision", {}).get("enabled", False):
            self.sprite.visao = "desligada"
        else:
            self.sprite.visao = "pausada" if self.agent.paused or self._congelado() else "ligada"
        self.tray.icon.setToolTip(f"Neku: visão {self.sprite.visao}")

    def _agent_tick(self):
        now = time.monotonic()
        dt, self._last_agent_tick = now - self._last_agent_tick, now
        self._update_indicator()
        if self._congelado():
            return
        rate = self.brain.motor_activity().get("AJUDAR", 0.0)
        talking = self.chat.busy or self.chat.pending_confirm is not None or self.chat.bubble.input.hasFocus()
        self.agent.tick(dt, rate, self.activity, self.pet_state.emotion, talking)
        settings = self.settings_neko
        if settings.get("monitor_active_app", False) and not settings.get("observation_paused", False):
            self.neko_observer.poll()

    def _check_downloads(self):
        for path in self.habits.check():
            def task(path=path):
                self.chat._work(lambda: self.habits.handle_zip(path, self.chat.progress_ready.emit))
            threading.Thread(target=task, daemon=True).start()

    def _refresh_downloads(self):
        folder = str(files.known_folder("downloads"))
        if self.settings_neko.get("watch_downloads", False):
            if folder not in self.watcher.directories():
                self.watcher.addPath(folder)
            self.pulse.start(DOWNLOAD_CHECK_MS)
        else:
            if self.watcher.directories():
                self.watcher.removePaths(self.watcher.directories())
            self.pulse.stop()

    def _refresh_all(self):
        self.habits.start()
        self._refresh_downloads()
        self._update_vision()

    # ---------- menus e janelas ----------

    def open_memory(self):
        if self.memories is None or not self.memories.isVisible():
            self.memories = MemoryDialog(self.neko_memory)
        self.memories.show()
        self.memories.raise_()
        self.memories.activateWindow()

    def open_agent_settings(self):
        dialog = SettingsDialog(self.settings_neko, self.neko_memory, self.journal)
        if dialog.exec():
            dialog.apply()
            self._refresh_all()
            if not sync_autostart(self.root, self.settings_neko):
                QMessageBox.warning(None, "Neku", "Salvei, mas não consegui ajustar a inicialização com o Windows.")

    def menu_alternar_notebook(self):
        super().menu_alternar_notebook()
        self.settings_neko.set("notebook_visible", not self.mesa.escondido)

    def toggle_vision_pause(self):
        self.agent.paused = not self.agent.paused
        self._update_indicator()

    def toggle_follow(self):
        self.settings_neko.set("follow_mouse", not self.settings_neko.get("follow_mouse", True))

    def show_pet_menu(self, pos):
        menu = QMenu()

        def item(target, text, fn, enabled=True):
            action = target.addAction(text)
            action.setEnabled(enabled)
            action.triggered.connect(fn)
            return action

        perms = self.perms
        item(menu, "Conversar", self.chat.open)
        item(menu, "Memórias", self.open_memory)
        menu.addSeparator()
        item(menu, "Retomar visão" if self.agent.paused else "Pausar visão", self.toggle_vision_pause,
             self.settings_neko.get("vision", {}).get("enabled", False))
        follow = item(menu, "Seguir o mouse enquanto digito", self.toggle_follow)
        follow.setCheckable(True)
        follow.setChecked(self.settings_neko.get("follow_mouse", True))
        item(menu, "Pedir para trabalhar", self.menu_pedir_trabalho)
        item(menu, "Pedir para dormir", self.menu_sleep, not self.asleep)
        play = menu.addMenu("Brincar")
        item(play, "Cutucar", self.menu_poke, perms["cutucar"])
        item(play, "Dar carinho", self.menu_caress, perms["carinho"])
        item(play, "Jogar a bolinha perto dele", self.menu_place_ball, perms["bolinha"])
        item(play, "Guardar a bolinha", self.menu_store_ball, perms["bolinha"] and not self.ball_stored)
        item(play, "Fazer uma travessura agora", self.menu_mischief, perms["travessuras"])
        item(play, "Mostrar o notebook" if self.mesa.escondido else "Esconder o notebook", self.menu_alternar_notebook)
        item(play, "Cantinho do castigo", lambda: self.castigo.toggle(self.bounds()))
        menu.addSeparator()
        item(menu, "Monitor neural", lambda: self.floats.toggle("neural"))
        item(menu, "Configurações do agente", self.open_agent_settings)
        item(menu, "Configurações do corpo", self.open_settings)
        menu.addSeparator()
        item(menu, "Esconder (volta pela bandeja)", self.toggle_hidden)
        item(menu, "Sair", self.quit)
        menu.exec(pos)

    # ---------- fim ----------

    def panic(self):
        super().panic()
        self.runtime.stop()
        self.chat.bubble.hide()
        self._update_indicator()

    def save(self):
        super().save()
        if hasattr(self, "agent") and not self.wiping:
            self.agent.save()

    def quit(self):
        try:
            if self.vision:
                self.vision.stop()
            self.settings_neko.data["window_pos"] = [int(self.pet.body.x), 0]
            self.settings_neko.save()
            self.hotkey_chat.close()
            self.runtime.stop()
            self.chat.close()
        except Exception:
            log.exception("Erro ao fechar o agente")
        finally:
            super().quit()

def run(root):
    app = QApplication(sys.argv)
    app.setApplicationName("Neku")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    engine_config.APP_NOME = "Neku"
    (root/"data").mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root/"data"/"neko.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        log.info("Neku já está aberto; esta instância vai encerrar")
        QMessageBox.information(None, "Neku", "O Neku já está aberto.")
        return 0
    log.info("Neku %s iniciado", __version__)
    paths = Paths(root=root, dados=root/"data"/"cerebro")
    first_time = not paths.permissions.exists()
    store = SettingsStore(paths)
    if first_time:
        store.update(ENGINE_DEFAULTS)
    if not store.perms["ativo"]:
        dialog = BodySettings(store.perms, paths, first_run=True)
        dialog.changed.connect(store.update)
        if not dialog.exec():
            return 0
    neko = NekoApp(store, paths, root)
    config = neko.settings_neko
    if config.backup_path:
        QMessageBox.warning(None, "Neku", f"As configurações tinham problemas e foram corrigidas.\n\nCópia do original:\n{config.backup_path}")
    sync_autostart(root, config)
    code = app.exec()
    lock.unlock()
    log.info("Neku encerrado (código %s)", code)
    return code
