"""
Configuração comum dos testes (pasta tests/).

- Qt sem janela: os testes rodam em qualquer máquina, sem abrir nada na tela.
- Isolamento: apps e janelas criados num teste não continuam rodando nos seguintes.
"""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _encerrar_apps_e_janelas():
    from PySide6.QtWidgets import QApplication
    qt = QApplication.instance()
    antes = set(qt.topLevelWidgets()) if qt else set()
    yield
    from PySide6.QtCore import QTimer
    from pestinha.app import PestinhaApp
    for obj in gc.get_objects():
        if isinstance(obj, PestinhaApp):
            for timer in obj.findChildren(QTimer):
                timer.stop()
    qt = QApplication.instance()
    if qt:
        for widget in set(qt.topLevelWidgets()) - antes:
            for timer in widget.findChildren(QTimer):
                timer.stop()
            widget.close()


SEM_IMAGENS = {
    "test_conteudo_do_bryan_esta_na_pasta_dele", "test_jorge_tem_conteudo_proprio_completo", "test_jorge_no_app",
}


def pytest_collection_modifyitems(items):
    """Estes testes exigem imagens do Pestinha que não foram incorporadas ao Neku (veja NOTICE.md)."""
    for item in items:
        if item.name in SEM_IMAGENS:
            item.add_marker(pytest.mark.skip(reason="depende de imagens não incorporadas"))
