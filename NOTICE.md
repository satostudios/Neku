# Origem do código

Neku, uma parceria da Sato Studios com a Vetra. Copyright (C) 2026 Sato Studios e Vetra.

O Neku, antes chamado Neko, usa o motor do **Pestinha**, de mille-okws: https://github.com/mille-okws/pestinha
Versão incorporada: commit `984fb86`, de 2026-11-04. O Pestinha é licenciado sob a GPL-3.0-or-later e, por
isso, o Neku como um todo também é distribuído sob a GPL-3.0-or-later (veja [LICENSE](LICENSE)). Os direitos
sobre o código original seguem com os autores do Pestinha.

## O que veio do Pestinha

| Pasta | Conteúdo |
|---|---|
| `src/pestinha/` | O motor inteiro: rede neural pulsada, física, emoções, corpo, travessuras, interface |
| `tests_pestinha/` | Os testes do motor |
| `docs/pestinha/` | Documentação de arquitetura e da rede neural |
| `ferramentas/` | Fuzzer e geradores de documentação, exceto `gerar_midia.py`, que é do Neku |
| `pets/bryan*`, `pets/jorge*` | Personagens originais, só com textos e configurações |

## O que foi alterado no motor

Alterações feitas em novembro de 2026.

Só pontos de encaixe; nenhum comportamento original foi removido.

- `paths.py`: a raiz do programa passou a ser a pasta do projeto.
- `config.py`: nova permissão `protesto`, ligada por padrão no motor.
- `body/pet.py`: tamanho do corpo e desenho configuráveis.
- `body/behavior.py`: `seguir_x`, para acompanhar um ponto.
- `app.py`: `QUADRO_MS`, `_criar_pet`, `sinais_extras`, `recompensa_extra` e `pode_protestar`.
- `src/pestinha/principal.py`: cópia do `main.py` original, usada pelos testes do motor.
- `tests_pestinha/`: caminhos ajustados para `src/pestinha` e importações de `pestinha.principal`.
- `conftest.py`, na raiz: pula os 3 testes que dependem das imagens que não foram copiadas.

A rede neural não foi editada: `src/neko/brain.py` acrescenta os canais `TELA` e `ERRO` e o motor `AJUDAR` ao iniciar.

## O que não foi copiado

- `assets/`, porque o próprio Pestinha informa que imagens e textos dessa pasta não estão cobertos pela licença do código.
  A única exceção é `assets/comum/programas.json`, um esqueleto de categorias vazias, sem imagem nem texto, exigido pelos testes do motor.
- `pets/*/memes/`, imagens que podem ter direitos de terceiros.
- `executáveis/`, o `Pestinha.exe` pronto.
- `instalador/` e `.github/`, porque o Neko tem instalador próprio.
