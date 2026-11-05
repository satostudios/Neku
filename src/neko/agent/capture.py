"""Leitura da tela e das janelas pela API do Windows. A imagem fica só na memória e nunca vai para o disco."""
import ctypes, logging, sys
from ctypes import wintypes
from dataclasses import dataclass
import numpy as np
import psutil

log = logging.getLogger(__name__)

SRCCOPY = 0x00CC0020
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
SIGNATURE_STEP = 24
CHANGE_THRESHOLD = 1.5

class _BitmapHeader(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]

def _gdi():
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = (wintypes.HWND,)
    user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
    gdi32.BitBlt.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HDC,
                             ctypes.c_int, ctypes.c_int, wintypes.DWORD)
    gdi32.GetDIBits.argtypes = (wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.UINT)
    gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
    gdi32.DeleteDC.argtypes = (wintypes.HDC,)
    return user32, gdi32

@dataclass
class Frame:
    pixels: np.ndarray
    left: int = 0
    top: int = 0

    def hide(self, rect):
        """Apaga uma área da imagem antes do OCR: janelas privadas e as do próprio Neku."""
        l, t, r, b = rect
        l, r = max(0, l - self.left), max(0, r - self.left)
        t, b = max(0, t - self.top), max(0, b - self.top)
        self.pixels[t:b, l:r] = 0

    def signature(self):
        return self.pixels[::SIGNATURE_STEP, ::SIGNATURE_STEP, 1].astype(np.int16)

def changed(before, after):
    """Compara duas assinaturas reduzidas: evita OCR quando a tela continua igual."""
    if before is None or before.shape != after.shape:
        return True
    return float(np.abs(before - after).mean()) > CHANGE_THRESHOLD

def grab():
    """Copia todos os monitores. Janelas protegidas pelo Windows, como vídeos com DRM, chegam pretas."""
    user32, gdi32 = _gdi()
    left, top = user32.GetSystemMetrics(SM_XVIRTUALSCREEN), user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width, height = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN), user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    previous = gdi32.SelectObject(memory, bitmap)
    try:
        if not gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, SRCCOPY):
            raise OSError("não foi possível copiar a tela")
        header = _BitmapHeader(ctypes.sizeof(_BitmapHeader), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        pixels = np.empty((height, width, 4), dtype=np.uint8)
        if not gdi32.GetDIBits(memory, bitmap, 0, height, pixels.ctypes.data, ctypes.byref(header), 0):
            raise OSError("não foi possível ler a tela")
    finally:
        gdi32.SelectObject(memory, previous)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)
    return Frame(pixels, left, top)

def window_info(hwnd):
    """(programa, título, retângulo em pixels físicos) de uma janela; None se ela sumiu."""
    import win32gui, win32process
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name().lower(), win32gui.GetWindowText(hwnd), win32gui.GetWindowRect(hwnd)
    except Exception:
        return None

def foreground():
    import win32gui
    hwnd = win32gui.GetForegroundWindow()
    return window_info(hwnd) if hwnd else None

def visible_windows():
    """Todas as janelas visíveis: uma janela privada aberta ao lado também precisa ser escondida."""
    import win32gui
    found = []

    def visit(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
            info = window_info(hwnd)
            if info:
                found.append(info)
        return True

    try:
        win32gui.EnumWindows(visit, None)
    except Exception:
        log.warning("Não foi possível listar as janelas")
    return found
