"""Política de cada capacidade. Excluir, mover e criar arquivos sempre pedem confirmação."""

CAPABILITIES = {
    "open_apps": "Abrir aplicativos",
    "open_web": "Abrir sites no navegador",
    "read_files": "Procurar nomes de arquivos nas suas pastas",
    "write_files": "Criar, mover e enviar arquivos para a Lixeira",
}
LEVEL_NAMES = {"deny": "Bloqueado", "ask": "Perguntar sempre", "allow": "Permitir sem perguntar"}

class Permissions:
    def __init__(self, config):
        self.config = config

    def level(self, capability):
        return self.config.get("permissions", {}).get(capability, "ask")

    def denied(self, capability):
        return self.level(capability) == "deny"

    def needs_confirmation(self, capability):
        return capability == "write_files" or self.level(capability) != "allow"
