import logging, os
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
                               QPushButton, QVBoxLayout)
from .memory.store import ChangedOnDisk, FILE_KINDS

log = logging.getLogger(__name__)

TITLES = {"user_profile.md": "Sobre você", "preferences.md": "Preferências", "projects.md": "Projetos",
          "important_memories.md": "Importante", "temporary.md": "Temporárias", "learned_behaviors.md": "Aprendizados",
          "linguajar.md": "Seu linguajar", "identity.md": "Identidade do Neku", "personality.md": "Personalidade do Neku"}

class MemoryDialog(QDialog):
    def __init__(self, memory):
        super().__init__()
        self.memory = memory
        self.current = None
        self.mtime = None
        self.names = list(TITLES)
        self.setWindowTitle("Memórias do Neku")
        self.resize(720, 480)
        self.files = QListWidget()
        self.files.addItems(TITLES.values())
        self.files.setFixedWidth(180)
        self.files.currentRowChanged.connect(self._select)
        self.editor = QPlainTextEdit()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar neste arquivo…")
        self.search.returnPressed.connect(self._find)
        self.status = QLabel("Antes de salvar, guardo um backup da versão anterior.")
        save = QPushButton("Salvar")
        folder = QPushButton("Abrir pasta")
        close = QPushButton("Fechar")
        save.clicked.connect(self.save)
        folder.clicked.connect(lambda: os.startfile(str(self.memory.memory_dir)))
        close.clicked.connect(self.close)
        right = QVBoxLayout()
        right.addWidget(self.search)
        right.addWidget(self.editor)
        row = QHBoxLayout()
        row.addWidget(self.status, 1)
        row.addWidget(folder)
        row.addWidget(close)
        row.addWidget(save)
        right.addLayout(row)
        layout = QHBoxLayout(self)
        layout.addWidget(self.files)
        layout.addLayout(right, 1)
        self.files.setCurrentRow(0)

    def _select(self, row):
        if self.current and self.editor.document().isModified() and not self._keep_going():
            self.files.blockSignals(True)
            self.files.setCurrentRow(self.names.index(self.current))
            self.files.blockSignals(False)
            return
        self.load(self.names[row])

    def _keep_going(self):
        return QMessageBox.question(self, "Neku", "Descartar as alterações que não foram salvas?") == QMessageBox.StandardButton.Yes

    def load(self, name):
        self.current = name
        self.memory.ensure_file(name)
        text, self.mtime = self.memory.read_file(name)
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)

    def save(self):
        try:
            self.mtime = self.memory.save_file(self.current, self.editor.toPlainText(), self.mtime)
        except ChangedOnDisk:
            QMessageBox.warning(self, "Neku", "Esse arquivo mudou por fora enquanto estava aberto. Reabra para não perder nada.")
            return False
        except OSError:
            log.exception("Não foi possível salvar a memória")
            QMessageBox.warning(self, "Neku", "Não consegui salvar esse arquivo.")
            return False
        self.editor.document().setModified(False)
        self.status.setText("Salvo. A versão anterior ficou no backup.")
        return True

    def _find(self):
        if not self.editor.find(self.search.text()):
            self.editor.moveCursor(self.editor.textCursor().MoveOperation.Start)
            self.editor.find(self.search.text())

    def closeEvent(self, event):
        if self.editor.document().isModified() and not self._keep_going():
            event.ignore()
            return
        event.accept()
