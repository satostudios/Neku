"""Gera as imagens e os GIFs de docs/midia com o sprite e o balão reais do Neku.

Nada aqui olha a tela: cada quadro é desenhado fora dela, com as frases que o programa realmente usa.
Precisa do Pillow (requirements-dev.txt). Uso: python ferramentas/gerar_midia.py
"""
import io, os, sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QBuffer, QIODevice, QRect
from PySide6.QtWidgets import QApplication
from neko.app import WELCOME
from neko.bubble import ChatBubble
from neko.companion import MODEL_ON
from neko.sprite import ALTURA, Sprite

OUT = ROOT / "docs" / "midia"
FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
BAR = 48
CARD, CREAM, YELLOW, TEAL, TEAL_DEEP = "#141A1F", "#F4F0B8", "#EDE96A", "#2E7D6B", "#215C50"
LETTERS = {"N": ("X...X", "XX..X", "X.X.X", "X.X.X", "X.X.X", "X..XX", "X...X"),
           "E": ("XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"),
           "K": ("X...X", "X..X.", "X.X..", "XX...", "X.X..", "X..X.", "X...X"),
           "U": ("X...X", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX.")}
EMOTIONS = (("observando", "observando"), ("feliz", "feliz"), ("curioso", "curioso"), ("bravo", "bravo"),
            ("triste", "triste"), ("assustado", "assustado"), ("dramatico", "dramático"), ("dormindo", "dormindo"))
LINE_ONE = "Consegue falar com a IA local?"
ANSWER_ONE = MODEL_ON.format(name="LFM2.5-350M-Q4_K_M")
LINE_TWO = "para de olhar"
ANSWER_TWO = "Fechei os olhos. Diga “volta a olhar” quando quiser."


def font(size, name="seguisb.ttf"):
    return ImageFont.truetype(str(FONTS / name), size)


def to_pil(picture):
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    picture.save(buffer, "PNG")
    return Image.open(io.BytesIO(bytes(buffer.data()))).convert("RGBA")


def neku(factor, when=0.0, walking=False, visao="desligada", atividade=None, **kwargs):
    body = SimpleNamespace(grounded=True, vx=100.0) if walking else None
    sprite = Sprite(body, unidade=1)
    sprite.visao, sprite.atividade = visao, atividade
    with mock.patch("neko.sprite.time.monotonic", return_value=when):
        image = to_pil(sprite.imagem(**kwargs))
    return image.resize((image.width * factor, image.height * factor), Image.Resampling.NEAREST)


def desktop(width, height):
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        mix = y / height
        draw.line(((0, y), (width, y)), fill=(int(36 - 18 * mix), int(58 - 32 * mix), int(66 - 36 * mix), 255))
    top = height - BAR
    draw.rectangle((0, top, width, height), fill="#0E1316")
    start = width // 2 - 92
    for index in range(5):
        draw.rounded_rectangle((start + index * 40, top + 10, start + index * 40 + 28, top + 38), 7, fill="#2B3640")
    return image


def stand(scene, image, factor, x):
    """Os pés do corpo encostam no topo da barra, como no programa."""
    y = scene.height - BAR - (ALTURA + 2) * factor
    scene.alpha_composite(image, (int(x), y))
    return y


def card(image, label, size):
    scene = Image.new("RGBA", size, CARD)
    scene.alpha_composite(image, ((size[0] - image.width) // 2, 8))
    draw = ImageDraw.Draw(scene)
    box = draw.textbbox((0, 0), label, font=font(24))
    draw.text(((size[0] - box[2]) // 2, size[1] - 44), label, font=font(24), fill=CREAM)
    return scene


def save_gif(name, frames, durations):
    paletted = [frame.convert("RGB").quantize(colors=96, dither=Image.Dither.NONE) for frame in frames]
    paletted[0].save(OUT / name, save_all=True, append_images=paletted[1:], duration=durations, loop=0, optimize=True, disposal=1)


def cover():
    scene = Image.new("RGBA", (1280, 640), TEAL_DEEP)
    draw = ImageDraw.Draw(scene)
    for position in range(0, 1280, 40):
        draw.line(((position, 0), (position, 640)), fill="#25665A")
        draw.line(((0, position), (1280, position)), fill="#25665A")
    scene.alpha_composite(neku(14, visao="ligada", emocao="feliz"), (120, 96))
    left, pixel = 610, 24
    for letter in "NEKU":
        for row, line in enumerate(LETTERS[letter]):
            for column, mark in enumerate(line):
                if mark == "X":
                    x, y = left + column * pixel, 120 + row * pixel
                    draw.rectangle((x + 6, y + 6, x + pixel + 5, y + pixel + 5), fill="#141414")
        for row, line in enumerate(LETTERS[letter]):
            for column, mark in enumerate(line):
                if mark == "X":
                    x, y = left + column * pixel, 120 + row * pixel
                    draw.rectangle((x, y, x + pixel - 1, y + pixel - 1), fill=CREAM)
        left += 6 * pixel
    draw.text((610, 330), "Agente de IA local para o Windows 11", font=font(36), fill=CREAM)
    draw.text((610, 386), "Vê sua tela, aprende com você, nada sai do PC", font=font(28, "segoeui.ttf"), fill=CREAM)
    draw.text((610, 452), "Sato Studios × Vetra", font=font(34), fill=YELLOW)
    scene.convert("RGB").save(OUT / "capa.png", optimize=True)


def walking():
    frames, width, factor = [], 640, 3
    path = [*range(30, 520, 16), *range(520, 300, -16)]
    for index, x in enumerate(path):
        scene = desktop(width, 170)
        stand(scene, neku(factor, index * 0.07, walking=True, visao="ligada", gaze=(1.0 if index < 31 else -1.0, 0.0)), factor, x)
        frames.append(scene)
    for blink, wait in ((1.0, 900), (0.0, 130), (1.0, 900)):
        scene = desktop(width, 170)
        stand(scene, neku(factor, 0.0, visao="ligada", emocao="contente", blink=blink), factor, path[-1])
        frames.append(scene)
    save_gif("andando.gif", frames, [70] * len(path) + [900, 130, 900])


def emotions():
    size, frames = (320, 300), []
    for key, label in EMOTIONS:
        frames.append(card(neku(8, 1.0, emocao=key), label, size))
    save_gif("emocoes.gif", frames, 850)
    sheet = Image.new("RGBA", (size[0] * 4, size[1] * 2), CARD)
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, ((index % 4) * size[0], (index // 4) * size[1]))
    sheet.convert("RGB").save(OUT / "emocoes.png", optimize=True)


def working():
    size, frames, durations = (320, 300), [], []
    states = (("olhando a tela", {"visao": "ligada"}, 8), ("pensando", {"visao": "ligada", "atividade": "pensando"}, 14),
              ("trabalhando", {"visao": "ligada", "atividade": "trabalhando"}, 14),
              ("pronto", {"visao": "ligada", "emocao": "feliz"}, 8), ("visão pausada", {"visao": "pausada", "emocao": "dormindo"}, 8))
    moment = 0.0
    for label, options, count in states:
        for _ in range(count):
            moment += 0.12
            frames.append(card(neku(8, moment, **options), label, size))
            durations.append(120)
    save_gif("trabalhando.gif", frames, durations)


def bubble_scene(bubble, width, height, factor, **options):
    scene = desktop(width, height)
    x = (width - 28 * factor) // 2
    head = stand(scene, neku(factor, **options), factor, x)
    bubble.place_near(QRect(0, 3000, 48, 52))
    picture = to_pil(bubble.grab().toImage())
    scene.alpha_composite(picture, ((width - picture.width) // 2, max(0, head + 10 - picture.height)))
    return scene


def permission():
    bubble = ChatBubble()
    bubble.say(WELCOME)
    bubble.ask("Posso?", "Pode", "Agora não")
    bubble._flush()
    bubble._render()
    bubble_scene(bubble, 520, 760, 3, emocao="feliz").convert("RGB").save(OUT / "autorizacao.png", optimize=True)


def conversation():
    bubble = ChatBubble()
    frames, durations = [], []

    def show(wait, **options):
        bubble._render()
        frames.append(bubble_scene(bubble, 520, 420, 3, **options))
        durations.append(wait)

    def exchange(line, answer, **done):
        bubble.add_user(line)
        bubble.begin_answer()
        for step in range(5):
            show(150, when=step * 0.2, visao="ligada", atividade="pensando")
        for size in range(0, len(answer) + 3, 3):
            bubble.turns[-1] = ("neko", answer[:size])
            show(45, **done)
        durations[-1] = 2400

    exchange(LINE_ONE, ANSWER_ONE, visao="ligada", emocao="feliz")
    exchange(LINE_TWO, ANSWER_TWO, visao="pausada", emocao="dormindo")
    save_gif("conversa.gif", frames, durations)


def main():
    app = QApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    neku(8, emocao="feliz", visao="ligada").save(OUT / "neku.png", optimize=True)
    cover()
    walking()
    emotions()
    working()
    permission()
    conversation()
    for path in sorted(OUT.iterdir()):
        print(f"{path.name}: {path.stat().st_size // 1024} KB")
    app.quit()


if __name__ == "__main__":
    main()
