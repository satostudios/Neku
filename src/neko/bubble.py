"""Conversa em balão: sem janelas modais, com a resposta aparecendo enquanto o Neku fala."""
import html, math
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QTextDocument
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QTextBrowser, QVBoxLayout, QWidget
INK, PAPER = QColor("#141414"), QColor("#F4F0B8")

WIDTH = 340
TAIL = 13
MARGIN = 8
MAX_TURNS = 14
REVEAL_STEP = 3
HIDE_AFTER_MS = 25000
VIEW_HEIGHT = 170
CHROME_HEIGHT = 100

STYLE = """
QTextBrowser { background: transparent; border: none; color: #10141A; font: 10.5pt "Segoe UI"; }
QLineEdit { background: #EEF2F8; border: 2px solid #C9D3E1; border-radius: 12px; padding: 6px 10px;
            color: #10141A; font: 10.5pt "Segoe UI"; }
QLineEdit:focus { border-color: #2E7D6B; }
QPushButton { background: #EEF2F8; border: 2px solid #C9D3E1; border-radius: 12px; padding: 5px 14px;
              color: #10141A; font: 600 10pt "Segoe UI"; }
QPushButton:hover { border-color: #2E7D6B; }
QPushButton#primary { background: #2E7D6B; border-color: #141414; color: #F4F0B8; }
QPushButton#primary:hover { background: #215C50; border-color: #141414; color: #EDE96A; }
"""

class ChatBubble(QWidget):
    submitted = Signal(str)
    answered = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Conversa com o Neku")
        self.setFixedWidth(WIDTH)
        self.setStyleSheet(STYLE)
        self.turns = []
        self.pending = ""
        self.last_sent = ""
        self.tail_below = True
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFixedHeight(VIEW_HEIGHT)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Fale comigo…")
        self.input.setMaxLength(1000)
        self.input.returnPressed.connect(self._send)
        self.input.textChanged.connect(self._hold)
        self.yes = QPushButton("Sim")
        self.yes.setObjectName("primary")
        self.no = QPushButton("Não")
        self.yes.clicked.connect(lambda: self._answer(True))
        self.no.clicked.connect(lambda: self._answer(False))
        self.choices = QWidget()
        row = QHBoxLayout(self.choices)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch()
        row.addWidget(self.no)
        row.addWidget(self.yes)
        self.choices.hide()
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(MARGIN + 8, MARGIN + 8, MARGIN + 8, MARGIN + 8 + TAIL)
        self.layout_box.setSpacing(8)
        self.layout_box.addWidget(self.view)
        self.layout_box.addWidget(self.choices)
        self.layout_box.addWidget(self.input)
        self.reveal = QTimer(self)
        self.reveal.setInterval(16)
        self.reveal.timeout.connect(self._reveal_step)
        self.hider = QTimer(self)
        self.hider.setSingleShot(True)
        self.hider.setInterval(HIDE_AFTER_MS)
        self.hider.timeout.connect(self._auto_hide)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = MARGIN + (0 if self.tail_below else TAIL)
        bottom = self.height() - MARGIN - (TAIL if self.tail_below else 0)
        rect = QRectF(MARGIN, top, self.width() - MARGIN * 2, bottom - top)
        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)
        tail = QPainterPath()
        center = rect.center().x()
        if self.tail_below:
            tail.moveTo(center - 15, rect.bottom() - 1)
            tail.quadTo(center - 4, rect.bottom() + 6, center, rect.bottom() + TAIL)
            tail.quadTo(center + 6, rect.bottom() + 6, center + 15, rect.bottom() - 1)
        else:
            tail.moveTo(center - 15, rect.top() + 1)
            tail.quadTo(center - 4, rect.top() - 6, center, rect.top() - TAIL)
            tail.quadTo(center + 6, rect.top() - 6, center + 15, rect.top() + 1)
        tail.closeSubpath()
        shape = path.united(tail)
        painter.setPen(QPen(INK, 3))
        painter.setBrush(PAPER)
        painter.drawPath(shape)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() == Qt.Key.Key_Up and not self.input.text():
            self.input.setText(self.last_sent)
        else:
            super().keyPressEvent(event)

    def place_near(self, rect):
        """Fica acima do Neku quando há espaço; senão, abaixo. Sempre dentro da tela dele."""
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.adjustSize()
        height = self.sizeHint().height()
        below = rect.top() - height + 14 < area.top()
        if below != (not self.tail_below):
            self.tail_below = not below
            top_margin = MARGIN + 8 + (TAIL if below else 0)
            bottom_margin = MARGIN + 8 + (0 if below else TAIL)
            self.layout_box.setContentsMargins(MARGIN + 8, top_margin, MARGIN + 8, bottom_margin)
        y = rect.bottom() - 18 if below else rect.top() - height + 14
        x = rect.center().x() - self.width() // 2
        self.move(max(area.left(), min(x, area.right() - self.width())),
                  max(area.top(), min(y, area.bottom() - height)))

    def open(self):
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()
        self.hider.stop()

    def show_passive(self):
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.show()
        self.hider.start()

    def add_user(self, text):
        self._flush()
        self._add("você", text)

    def begin_answer(self):
        self._flush()
        self._add("neko", "")

    def append(self, text):
        self.pending += text
        if not self.reveal.isActive():
            self.reveal.start()

    def say(self, text):
        self.begin_answer()
        self.append(text)

    def replace_answer(self, text):
        """Troca o que está sendo revelado pela resposta final, sem repetir o que já apareceu."""
        shown = self.turns[-1][1] if self.turns and self.turns[-1][0] == "neko" else ""
        if text.startswith(shown):
            self.pending = text[len(shown):]
            if self.pending and not self.reveal.isActive():
                self.reveal.start()
        else:
            self.pending = ""
            self.turns[-1:] = [("neko", text)]
            self._render()

    def ask(self, question, yes="Sim", no="Não"):
        self.append("\n\n" + question)
        self.yes.setText(yes)
        self.no.setText(no)
        self.input.hide()
        self.choices.show()
        self.hider.stop()
        self._fit_question()

    def _fit_question(self):
        """Quem responde precisa ver a pergunta inteira sem rolar: às vezes ela é um pedido de autorização."""
        if not self.turns:
            return
        who, text = self.turns[-1]
        self.view.ensurePolished()
        document = QTextDocument()
        document.setDefaultFont(self.view.font())
        document.setTextWidth(WIDTH - 2 * (MARGIN + 8))
        document.setHtml(self._row(who, text + self.pending))
        screen = self.screen() or QGuiApplication.primaryScreen()
        room = screen.availableGeometry().height() - CHROME_HEIGHT
        self.view.setFixedHeight(max(VIEW_HEIGHT, min(room, math.ceil(document.size().height()))))

    def clear_question(self):
        self.choices.hide()
        self.input.show()
        self.view.setFixedHeight(VIEW_HEIGHT)

    @property
    def waiting_answer(self):
        return not self.choices.isHidden()

    def _answer(self, value):
        self.clear_question()
        if self.isActiveWindow():
            self.input.setFocus()
        self.answered.emit(value)

    def _send(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.last_sent = text
        self.submitted.emit(text)

    def _hold(self):
        self.hider.stop()

    def _auto_hide(self):
        if not self.input.text() and not self.waiting_answer and not self.pending:
            self.hide()

    def _add(self, who, text):
        self.turns.append((who, text))
        self.turns = self.turns[-MAX_TURNS:]
        self._render()

    def _flush(self):
        if self.pending and self.turns:
            who, text = self.turns[-1]
            self.turns[-1] = (who, text + self.pending)
        self.pending = ""
        self.reveal.stop()

    def _reveal_step(self):
        if not self.pending or not self.turns:
            self.reveal.stop()
            if self.isVisible() and not self.input.hasFocus() and not self.waiting_answer:
                self.hider.start()
            return
        chunk, self.pending = self.pending[:REVEAL_STEP], self.pending[REVEAL_STEP:]
        who, text = self.turns[-1]
        self.turns[-1] = (who, text + chunk)
        self._render()

    @staticmethod
    def _row(who, text):
        safe = html.escape(text).replace("\n", "<br>")
        if who == "você":
            return f'<p align="right" style="color:#5B6778;margin:2px 0 8px 40px">{safe}</p>'
        return f'<p style="margin:2px 28px 10px 0">{safe}</p>'

    def _render(self):
        self.view.setHtml("".join(self._row(who, text) for who, text in self.turns))
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def transcript(self):
        return "\n".join(f"{who}: {text}" for who, text in self.turns)
