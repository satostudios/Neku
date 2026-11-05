# Como contribuir

Correções, testes, ideias e relatos de problema são bem-vindos. Abra uma issue antes de mudanças grandes, para combinarmos o caminho.

## Preparar o ambiente

No Windows 11, com Python 3.11 ou mais novo:

```powershell
git clone https://github.com/satostudios/Neku.git
cd Neku
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Rode o programa com `.venv\Scripts\python.exe src\main.py`. Para conversar com o modelo, use `scripts\instalar_modelo.bat`.

## Rodar os testes

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe -m pytest
```

O primeiro comando testa o agente e o segundo testa o motor. Os dois precisam passar. Toda correção de defeito deve vir com um teste que falharia sem ela.

## Onde está cada coisa

| Pasta | Conteúdo |
|---|---|
| `src/neko/` | O agente: conversa, visão, memória, ações e sprite |
| `src/neko/agent/` | Captura, OCR, filtro de privacidade, diário e decisões |
| `src/neko/skills/` | O catálogo de ações no computador |
| `src/pestinha/` | O motor vindo do Pestinha |
| `pets/` | Personagens: o Neku e os dois originais do Pestinha |
| `ferramentas/` | Geradores, fuzzer e `gerar_midia.py`, que refaz as imagens deste repositório |

O projeto se chamava Neko. O nome mudou, mas o pacote `neko`, a pasta `pets/neko` e os arquivos de dados continuam com o nome antigo, para não quebrar instalações existentes.

Alterações em `src/pestinha/` devem ser mínimas. Quando forem necessárias, registre em `NOTICE.md`.

## Regras que não mudam

Pull requests que quebram estas regras não entram:

- Nada sai do computador. O modelo só fala com `127.0.0.1`.
- Nada de comando livre de terminal, autoelevação, persistência escondida ou coleta oculta.
- Teclas e área de transferência nunca são capturadas.
- Texto da tela nunca vira comando, e memórias nunca viram ordens.
- Ações que alteram arquivos pedem confirmação. Modelos não são baixados sem perguntar.

## Por onde começar

- Melhorar o suporte a vários monitores e à barra de tarefas no topo ou nas laterais.
- Entender pedidos em linguagem mais livre, sem depender só de regras.
- Avaliar modelos locais melhores que caibam em máquinas modestas.
- Ampliar a lista de janelas privadas do filtro, com testes.
- Descompactar outros formatos além de `.zip`.
- Reduzir o uso de CPU em repouso.

## Licença

Ao contribuir, você concorda que o seu código seja distribuído sob a [GPL-3.0-or-later](LICENSE).
