"""O corpo do Neku em pixel art: uma grade pequena, sem antialiasing, com o rosto na tela do monitor."""
import math, time
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

UNIDADE = 2
LARGURA, ALTURA = 24, 26
CORPO = (LARGURA * UNIDADE, ALTURA * UNIDADE)
LADO_JANELA = 120

TINTA = QColor("#141414")
CASCA = QColor("#B39C6B")
CASCA_ESCURA = QColor("#7A6841")
CREME = QColor("#F4F0B8")
TELA = QColor("#2E7D6B")
TELA_FUNDA = QColor("#215C50")
ROSTO = QColor("#EDE96A")
VISAO_LIGADA = QColor("#7CFF6B")
VISAO_PAUSADA = QColor("#FF8A3C")

# (x, y, largura, altura) em unidades da grade.
OLHOS = {
    "feliz": ((10, 6, 3, 1), (9, 7, 1, 1), (13, 7, 1, 1), (16, 6, 3, 1), (15, 7, 1, 1), (19, 7, 1, 1)),
    "contente": ((10, 6, 3, 1), (9, 7, 1, 1), (13, 7, 1, 1), (16, 6, 3, 1), (15, 7, 1, 1), (19, 7, 1, 1)),
    "bravo": ((10, 5, 1, 1), (11, 6, 1, 1), (12, 7, 2, 1), (18, 5, 1, 1), (17, 6, 1, 1), (15, 7, 2, 1)),
    "triste": ((13, 5, 1, 1), (12, 6, 1, 1), (10, 7, 2, 1), (15, 5, 1, 1), (16, 6, 1, 1), (17, 7, 2, 1)),
    "assustado": ((10, 5, 3, 3), (16, 5, 3, 3)),
    "dramatico": ((10, 5, 1, 1), (12, 5, 1, 1), (11, 6, 1, 1), (10, 7, 1, 1), (12, 7, 1, 1),
                  (16, 5, 1, 1), (18, 5, 1, 1), (17, 6, 1, 1), (16, 7, 1, 1), (18, 7, 1, 1)),
    "dormindo": ((10, 7, 3, 1), (16, 7, 3, 1)),
    "curioso": ((11, 6, 2, 2), (16, 5, 3, 3)),
}
OLHOS_PADRAO = ((11, 6, 2, 2), (16, 6, 2, 2))
BOCAS = {
    "feliz": ((11, 9, 1, 1), (12, 10, 5, 1), (17, 9, 1, 1), (13, 11, 3, 1)),
    "contente": ((11, 9, 1, 1), (12, 10, 5, 1), (17, 9, 1, 1)),
    "observando": ((12, 10, 5, 1),),
    "curioso": ((14, 10, 2, 1),),
    "bravo": ((12, 11, 1, 1), (13, 10, 3, 1), (16, 11, 1, 1)),
    "triste": ((12, 11, 1, 1), (13, 10, 3, 1), (16, 11, 1, 1)),
    "assustado": ((13, 10, 3, 2),),
    "dramatico": ((12, 10, 1, 1), (13, 11, 1, 1), (14, 10, 1, 1), (15, 11, 1, 1), (16, 10, 1, 1)),
    "dormindo": ((13, 10, 3, 1),),
}
BOCA_PADRAO = ((11, 9, 1, 1), (12, 10, 5, 1), (17, 9, 1, 1))

class Sprite:
    """Pinta o Neku com a origem no centro do corpo. Serve de `pintor` para a janela do motor."""
    def __init__(self, corpo=None, unidade=UNIDADE):
        self.corpo = corpo
        self.unidade = unidade
        self.visao = "desligada"        # "ligada" e "pausada" acendem o led, para ficar sempre à vista
        self.atividade = None           # "pensando" ou "trabalhando" tomam a tela no lugar do rosto

    def _quadro(self, p):
        p.save()
        p.scale(self.unidade, self.unidade)
        p.translate(-LARGURA / 2, -ALTURA / 2)
        return p

    @staticmethod
    def _bloco(p, x, y, largura, altura, cor):
        p.fillRect(QRectF(x, y, largura, altura), cor)

    def _cabeca(self, p):
        b = self._bloco
        b(p, 1, 5, 3, 7, TINTA)                 # alça lateral
        b(p, 2, 6, 2, 5, CASCA_ESCURA)
        b(p, 4, 1, 20, 14, TINTA)               # contorno com cantos cortados
        b(p, 5, 0, 18, 16, TINTA)
        b(p, 5, 1, 18, 14, CASCA)
        b(p, 5, 1, 2, 14, CASCA_ESCURA)
        b(p, 7, 1, 16, 14, CREME)
        b(p, 8, 2, 14, 12, TELA)
        b(p, 8, 2, 14, 1, TELA_FUNDA)
        b(p, 8, 2, 1, 12, TELA_FUNDA)

    def _pernas(self, p, passo, no_ar):
        b = self._bloco
        b(p, 9, 16, 10, 6, TINTA)               # tronco
        b(p, 10, 16, 8, 5, CASCA)
        b(p, 12, 17, 4, 3, CREME)
        erguida_esq = -1 if passo > 0 or no_ar else 0
        erguida_dir = -1 if passo < 0 or no_ar else 0
        for x, erguida in ((10, erguida_esq), (15, erguida_dir)):
            b(p, x, 22 + erguida, 3, 2, TINTA)
            b(p, x - 1, 24 + erguida, 4, 2, TINTA)
            b(p, x + 1, 22 + erguida, 1, 2, CASCA)  # o miolo claro mantém as pernas visíveis sobre a barra escura
            b(p, x, 24 + erguida, 2, 1, CASCA)

    def _led(self, p):
        cor = {"ligada": VISAO_LIGADA, "pausada": VISAO_PAUSADA}.get(self.visao)
        if cor is not None:
            self._bloco(p, 2, 8, 2, 2, cor)

    def _rosto(self, p, gaze, blink, emotion, carinho, agora):
        if self.atividade == "trabalhando":
            self._barra(p, agora)
            return
        if self.atividade == "pensando":
            self._pontos(p, agora)
            return
        emocao = "contente" if carinho else emotion
        dx = round(max(-1.0, min(1.0, gaze[0]))) if emocao not in ("dormindo", "dramatico") else 0
        dy = 1 if gaze[1] > 0.7 else 0
        fechado = blink < 0.5 and emocao not in ("feliz", "contente", "dormindo")
        olhos = OLHOS["dormindo"] if fechado else OLHOS.get(emocao, OLHOS_PADRAO)
        for x, y, largura, altura in olhos:
            self._bloco(p, x + dx, y + dy, largura, altura, ROSTO)
        for x, y, largura, altura in BOCAS.get(emocao, BOCA_PADRAO):
            self._bloco(p, x, y, largura, altura, ROSTO)
        if emocao == "dormindo":
            self._zzz(p, agora)

    def _zzz(self, p, agora):
        subida = int(agora * 2) % 3
        for x, y in ((19, 5 - subida), (20, 5 - subida), (19, 6 - subida), (20, 7 - subida), (19, 7 - subida)):
            if y >= 2:
                self._bloco(p, x, y, 1, 1, ROSTO)

    def _pontos(self, p, agora):
        ativo = int(agora * 3) % 3
        for indice in range(3):
            y = 7 if indice == ativo else 8
            self._bloco(p, 11 + indice * 3, y, 2, 2, ROSTO)

    def _barra(self, p, agora):
        self._bloco(p, 10, 7, 10, 3, TELA_FUNDA)
        preenchido = int(agora * 6) % 11
        if preenchido:
            self._bloco(p, 10, 7, preenchido, 3, ROSTO)

    def __call__(self, p, shape, gaze=(0.0, 0.0), blink=1.0, emotion="observando", carinho=False, aparencia=None):
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        agora = time.monotonic()
        body = self.corpo
        andando = bool(body) and body.grounded and abs(body.vx) > 20
        passo = math.sin(agora * 14) if andando else 0.0
        no_ar = bool(body) and not body.grounded
        self._quadro(p)
        self._pernas(p, passo, no_ar)
        self._cabeca(p)
        self._led(p)
        self._rosto(p, gaze, blink, emotion, carinho, agora)
        p.restore()

    def imagem(self, emocao="observando", escala=1, gaze=(0.0, 0.0), blink=1.0, carinho=False, fundo=None):
        """Um quadro isolado: serve para o ícone da bandeja e para conferir o desenho."""
        largura, altura = (LARGURA + 4) * self.unidade * escala, (ALTURA + 4) * self.unidade * escala
        imagem = QImage(int(largura), int(altura), QImage.Format.Format_ARGB32_Premultiplied)
        imagem.fill(fundo or Qt.GlobalColor.transparent)
        p = QPainter(imagem)
        p.translate(largura / 2, altura / 2)
        p.scale(escala, escala)
        self(p, None, gaze, blink, emocao, carinho)
        p.end()
        return imagem
