import logging
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget)
from .config import CHOICES
from .permissions import CAPABILITIES, LEVEL_NAMES

log = logging.getLogger(__name__)

OBSERVE_CONSENT = ("Com isso ligado, o Neku registra neste computador:\n\n"
                   "• o nome do programa em primeiro plano, como chrome.exe\n"
                   "• o horário aproximado, em blocos de 15 minutos\n\n"
                   "Ele não vê títulos, janelas, sites, teclas nem arquivos, e nada sai do computador.\n\nLigar?")
DOWNLOADS_CONSENT = ("Com isso ligado, o Neku acompanha a pasta Downloads:\n\n"
                     "• percebe arquivos novos e guarda só a extensão, como .zip\n"
                     "• percebe quando você descompacta algo, para aprender o hábito\n\n"
                     "Ele não lê o conteúdo dos arquivos e nada sai do computador. Depois de aprender, ele pergunta "
                     "antes de assumir qualquer tarefa.\n\nLigar?")

VISION_CONSENT = ("Com isso ligado, o Neku lê a cada poucos segundos o texto que aparece em todos os monitores e guarda esse texto neste computador por alguns dias, para aprender com você e responder sobre o que viu.\n\n"
                  "Nada sai do computador e nenhuma imagem é guardada. Mensagens e documentos abertos serão lidos, exceto janelas de senha, bancos e navegação anônima.\n\nLigar?")

class SettingsDialog(QDialog):
    def __init__(self, config, memory=None, journal=None):
        super().__init__()
        self.config, self.memory, self.journal = config, memory, journal
        self.setWindowTitle("Configurações do Neku")
        self.setMinimumWidth(480)
        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "Geral")
        tabs.addTab(self._vision_tab(), "Visão")
        tabs.addTab(self._privacy_tab(), "Privacidade")
        tabs.addTab(self._permissions_tab(), "Permissões")
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        buttons = QHBoxLayout()
        save, cancel = QPushButton("Salvar"), QPushButton("Cancelar")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _general_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self.startup = QCheckBox("Iniciar junto com o Windows")
        self.startup.setChecked(self.config.get("start_with_windows",False))
        self.follow = QCheckBox("Seguir o mouse enquanto você digita ou usa o PC")
        self.follow.setChecked(self.config.get("follow_mouse",True))
        self.reduced = QCheckBox("Reduzir animações")
        self.reduced.setChecked(self.config.get("animation_level","full") == "reduced")
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.75, 2.0)
        self.scale.setSingleStep(0.25)
        self.scale.setValue(self.config.get("scale",1.0))
        self.zip = QCheckBox("Verificar e descompactar .zip novos sozinho")
        self.zip.setChecked(self.config.get("automations",{}).get("extract_zip",False))
        form.addRow(self.startup)
        form.addRow(self.follow)
        form.addRow(self.reduced)
        form.addRow("Tamanho (ao reabrir):", self.scale)
        form.addRow(self.zip)
        form.addRow(QLabel("Atalho para chamar o Neku: Ctrl+Alt+N"))
        return tab

    def _vision_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        vision = self.config.get("vision",{})
        self.vision = QCheckBox("Ler o texto que aparece na minha tela")
        self.vision.setChecked(vision.get("enabled",False))
        self.interval = QSpinBox()
        self.interval.setRange(3, 300)
        self.interval.setSuffix(" s")
        self.interval.setValue(vision.get("interval_seconds",8))
        self.retention = QSpinBox()
        self.retention.setRange(1, 90)
        self.retention.setSuffix(" dias")
        self.retention.setValue(vision.get("retention_days",7))
        self.titles = QLineEdit(", ".join(vision.get("ignored_titles",[])))
        self.titles.setPlaceholderText("exemplo: planilha de salários, prontuário")
        form.addRow(self.vision)
        form.addRow("Olhar a cada:", self.interval)
        form.addRow("Guardar o diário por:", self.retention)
        form.addRow("Títulos ignorados:", self.titles)
        notice = QLabel("Fica tudo neste computador. Só o texto é guardado, nunca imagens. Janelas de senha, bancos e navegação anônima são escondidas antes da leitura, e CPF, cartões e senhas digitadas são ocultados. Led verde: olhando.")
        notice.setWordWrap(True)
        form.addRow(notice)
        clear = QPushButton("Apagar tudo o que ele leu")
        clear.clicked.connect(self.clear_journal)
        form.addRow(clear)
        return tab

    def clear_journal(self):
        answer = QMessageBox.question(self, "Neku", "Apagar todo o diário da tela?")
        if answer == QMessageBox.StandardButton.Yes and self.journal:
            self.journal.clear()
            QMessageBox.information(self, "Neku", "Diário apagado.")

    def _privacy_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self.monitor = QCheckBox("Observar apenas o nome do app em primeiro plano")
        self.monitor.setChecked(self.config.get("monitor_active_app",False))
        self.downloads = QCheckBox("Acompanhar a pasta Downloads para aprender hábitos")
        self.downloads.setChecked(self.config.get("watch_downloads",False))
        self.language = QCheckBox("Aprender meu linguajar com o que escrevo para o Neku")
        self.language.setChecked(self.config.get("learn_language",True))
        self.history = QCheckBox("Guardar minhas mensagens no diário")
        self.history.setChecked(self.config.get("save_chat_history",False))
        self.ignored = QLineEdit(", ".join(self.config.get("ignored_apps",[])))
        self.ignored.setPlaceholderText("exemplo: banco.exe, steam.exe")
        form.addRow(self.monitor)
        form.addRow(self.downloads)
        form.addRow(self.language)
        form.addRow(self.history)
        form.addRow("Apps ignorados:", self.ignored)
        notice = QLabel("Teclas, telas, clipboard e conteúdo de janelas nunca são capturados. O diário é texto comum: "
                        "com ele ligado, tudo o que você digitar na conversa fica salvo, inclusive senhas.")
        notice.setWordWrap(True)
        form.addRow(notice)
        row = QHBoxLayout()
        export, clear = QPushButton("Exportar registros"), QPushButton("Apagar registros")
        export.clicked.connect(self.export_events)
        clear.clicked.connect(self.clear_events)
        row.addWidget(export)
        row.addWidget(clear)
        form.addRow(row)
        return tab

    def _permissions_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self.levels = {}
        current = self.config.get("permissions",{})
        for capability, label in CAPABILITIES.items():
            box = QComboBox()
            for level in CHOICES[capability]:
                box.addItem(LEVEL_NAMES[level], level)
            box.setCurrentIndex(max(0, box.findData(current.get(capability,"ask"))))
            self.levels[capability] = box
            form.addRow(label + ":", box)
        notice = QLabel("Criar, mover e mandar para a Lixeira sempre pedem confirmação. O Neku nunca executa "
                        "comandos livres, nunca apaga de forma definitiva e nunca abre sozinho o que baixou.")
        notice.setWordWrap(True)
        form.addRow(notice)
        return tab

    def export_events(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar registros", "registros-neko.json", "JSON (*.json)")
        if path and self.memory:
            QMessageBox.information(self, "Neku", f"{self.memory.export_events(path)} registro(s) exportado(s).")

    def clear_events(self):
        answer = QMessageBox.question(self, "Neku", "Apagar todos os registros de observação e eventos? Suas memórias em Markdown não são afetadas.")
        if answer == QMessageBox.StandardButton.Yes and self.memory:
            self.memory.clear_events()
            QMessageBox.information(self, "Neku", "Registros apagados.")

    def _consented(self, box, key, text):
        if not box.isChecked() or self.config.get(key,False):
            return box.isChecked()
        return QMessageBox.question(self, "Antes de ligar", text) == QMessageBox.StandardButton.Yes

    def apply(self):
        self.config.data["monitor_active_app"] = self._consented(self.monitor, "monitor_active_app", OBSERVE_CONSENT)
        self.config.data["watch_downloads"] = self._consented(self.downloads, "watch_downloads", DOWNLOADS_CONSENT)
        vision = self.config.data["vision"]
        if self.vision.isChecked() and not vision["enabled"]:
            vision["enabled"] = QMessageBox.question(self, "Antes de ligar", VISION_CONSENT) == QMessageBox.StandardButton.Yes
        elif not self.vision.isChecked():
            vision["enabled"] = False
        vision["interval_seconds"] = self.interval.value()
        vision["retention_days"] = self.retention.value()
        vision["ignored_titles"] = [title.strip() for title in self.titles.text().split(",") if title.strip()]
        self.config.data["start_with_windows"] = self.startup.isChecked()
        self.config.data["save_chat_history"] = self.history.isChecked()
        self.config.data["learn_language"] = self.language.isChecked()
        self.config.data["follow_mouse"] = self.follow.isChecked()
        self.config.data["animation_level"] = "reduced" if self.reduced.isChecked() else "full"
        self.config.data["scale"] = self.scale.value()
        self.config.data["ignored_apps"] = [name.strip() for name in self.ignored.text().split(",") if name.strip()]
        self.config.data["automations"]["extract_zip"] = self.zip.isChecked()
        for capability, box in self.levels.items():
            self.config.data["permissions"][capability] = box.currentData()
        self.config.save()
