"""OCR nativo do Windows: roda no computador, sem instalar modelo nem enviar nada para fora."""
import asyncio, logging

log = logging.getLogger(__name__)

class ScreenReader:
    def __init__(self, language="pt-BR"):
        self.language = language
        self.engine = None

    def available(self):
        return self._load() is not None

    def _load(self):
        if self.engine is None:
            try:
                from winrt.windows.globalization import Language
                from winrt.windows.media.ocr import OcrEngine
                self.engine = OcrEngine.try_create_from_language(Language(self.language)) or OcrEngine.try_create_from_user_profile_languages()
            except Exception:
                log.exception("OCR do Windows indisponível")
        return self.engine

    def read(self, pixels):
        """Devolve o texto de uma imagem BGRA (altura, largura, 4), uma linha por linha encontrada."""
        engine = self._load()
        if engine is None:
            return ""
        from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.storage.streams import DataWriter
        height, width = pixels.shape[:2]
        writer = DataWriter()
        writer.write_bytes(pixels.tobytes())
        bitmap = SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8, width, height,
                                                        BitmapAlphaMode.PREMULTIPLIED)

        async def recognize():
            return await engine.recognize_async(bitmap)

        result = asyncio.run(recognize())
        return "\n".join(line.text for line in result.lines)
