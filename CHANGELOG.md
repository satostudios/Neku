# Changelog

## 0.9.0 - 2026-11-05

Primeira versão pública.

- O projeto passa a se chamar Neku, uma parceria da Sato Studios com a Vetra. O pacote interno e os arquivos de dados
  continuam com o nome antigo, para não quebrar instalações existentes.
- Comandos aceitam "neku" e "neko" no começo da frase.
- Documentação pública, guia de contribuição, política de segurança e imagens geradas pelo próprio código.

## 0.8.1 - 2026-11-05

### Correções

- Quando o modelo repetia a pergunta, como em "oi", a resposta era descartada e o Neko dizia que não tinha conseguido
  falar com ele. O aviso agora só aparece quando o modelo realmente não responde.
- Perguntas sobre o modelo local são respondidas por um teste real de ida e volta, não pelo palpite do próprio modelo.
- O diagnóstico mostra o modelo embutido em vez de "LLM local: desligado".
- O prompt descreve um agente de IA local, não mais um gatinho, e pede frases completas em perguntas de conhecimento.

## 0.8.0 - 2026-11-04

O Neko deixa de ser um mascote e vira um agente de IA, com o motor do Pestinha como corpo e cérebro.

### Motor

- Incorporado o Pestinha inteiro (commit `984fb86`): rede neural pulsada, habituação, aprendizado de três
  fatores, condicionamento, memória episódica, homeostase, emoções, física, monitor neural, pânico, painéis,
  travessuras, protestos, cantinho do castigo, bolinha e notebook.
- O projeto passa a ser **GPL-3.0-or-later**. Origem e alterações em `NOTICE.md`.

### Corpo

- Novo personagem em pixel art, de 48×52 px, em cima da barra de tarefas e não mais solto pela tela.
- Led lateral mostra quando ele está lendo a tela.
- Anda pela barra acompanhando o cursor enquanto você digita.

### Visão e agente

- Lê o texto da tela com o OCR nativo do Windows, tudo local e sem guardar imagens.
- Tarja janelas de senha, bancos e navegação anônima, e oculta CPF, cartões e chaves antes de guardar.
- Diário da tela com busca e prazo de 7 dias.
- Novo neurônio motor `AJUDAR`, com canais `TELA` e `ERRO`: a rede decide quando oferecer ajuda.
- Sim e não viram recompensa na rede e na memória episódica.
- Aprende fluxos entre programas e assuntos frequentes; padrões entram como hipóteses.
- Texto na tela nunca vira comando.

### Comportamentos alterados

- A observação agora inclui o texto da tela, com consentimento. Antes, o projeto proibia capturar a tela.
- Removidos o rosto de gatinho, o movimento livre pela tela e o `mascot.py`.
- Fechar o Neko ou acionar o pânico cancela a partida do modelo em vez de esperar o carregamento, e a verificação de
  ociosidade não segura mais a interface. O pânico agora também desliga o servidor do modelo.
- Com uma pergunta aberta, o balão cresce até mostrar a mensagem inteira, para uma autorização nunca ficar fora de vista.

## 0.7.1 - 2026-11-04

Primeira versão validada com o modelo real, que revelou problemas invisíveis com o servidor simulado.

### Segurança

- O modelo obedecia a ordens escritas em memórias, apesar do aviso no prompt. Agora linhas com jeito de
  ordem não entram no prompt, embora continuem no arquivo, e só memórias ligadas à pergunta são enviadas.

### Honestidade

- Perguntas como "lembra de…?" são respondidas pela memória real, sem passar pelo modelo.
- Perguntas como "você abriu…?" têm resposta fixa, sem passar pelo modelo.
- Respostas em que o modelo afirma ter feito algo são barradas, e respostas que só repetem a pergunta
  são descartadas.

### Modelo

- Conversas de exemplo no prompt melhoram o tom, e a temperatura passa a 0,4.
- Padrão de 4 threads em prioridade baixa: rende o mesmo que 8 threads com metade da CPU.
- Respostas cortadas pelo limite de tokens terminam na última frase completa.

## 0.7.0 - 2026-11-04

Reúne as versões planejadas de 0.3 a 0.7: o Neko passa a lembrar, andar, agir e aprender.

### Memória real (0.3)

- Lembrar, consultar, corrigir e esquecer por conversa, em português e sem depender de modelo.
- Cada memória tem tipo, origem e data. Duplicatas não entram, e contradições simples perguntam antes.
- Novos `projects.md` e `temporary.md`, com anotações que expiram em 7 dias.
- Esquecer e corrigir sempre confirmam e fazem backup, preservando byte a byte o resto do arquivo.
- Senhas e documentos são recusados.
- Contexto escolhido por relevância, com orçamento único entre memória, histórico e resposta.
- Editor de memórias no menu, que avisa se o arquivo mudou por fora.

### Personagem e conversa (0.4)

- Novo design de gatinho, com rosto paramétrico e 12 expressões que se transformam suavemente.
- Piscadas variáveis, olhar que acompanha o cursor, squash & stretch, efeitos e pezinhos ao andar.
- Anda até perto do cursor enquanto você digita, sem cobri-lo e sem ler teclas.
- Conversa em balão, com a resposta aparecendo aos poucos, no lugar das janelas modais.
- Atalho global Ctrl+Alt+N, ícone na bandeja e boas-vindas na primeira abertura.
- Dorme quando você se afasta, sai da frente em tela cheia e lembra a posição ao reabrir.
- Reage à dificuldade das tarefas e evolui por estágios com o uso.

### Modelo local opcional (0.5)

- `scripts\instalar_modelo.bat` baixa llama.cpp e LFM2.5-350M com versões e SHA-256 fixados.
- Servidor iniciado sob demanda, só em `127.0.0.1`, encerrado junto com o Neko e descarregado quando ocioso.
- Respostas em tempo real. Sem modelo, ou se ele falhar, o Neko continua no modo básico.

### Ações, permissões e hábitos (0.6 e 0.7)

- Catálogo fechado de ações: apps, pastas, sites, busca por nome, zip, Defender, organização com
  desfazer, criar, mover, copiar, renomear, Lixeira, sistema, volume, bloqueio e avisos.
- Permissões por capacidade. Escrever sempre confirma e nada apaga de forma definitiva.
- Extração segura contra caminhos maliciosos, bombas e senhas, mantendo a marca da internet.
- Acompanha Downloads com consentimento, aprende o hábito de descompactar e pergunta antes de assumir.
- Aprende seu linguajar em `linguajar.md`, um arquivo editável.
- Observação com horários em blocos de 15 minutos, retenção de 30 dias, apps ignorados, exportação e
  exclusão, e pausa que sobrevive a reinícios.

## 0.2.0 - 2026-11-04

Versão de estabilidade e privacidade, sem recursos novos para o mascote.

### Privacidade e segurança

- Sair e Alt+F4 agora encerram o processo. Antes, ele continuava invisível e seguia observando.
- Mensagens não são mais gravadas por padrão. O diário virou opção e o SQLite não guarda mais conversa.
- O LLM só aceita endereços de loopback, ignora proxy e não segue redirecionamentos.
- A memória vai ao modelo em um bloco marcado como dado, e não pode fechar esse bloco.

### Confiabilidade

- `settings.json` inválido gera backup e aviso, em vez de ser sobrescrito. BOM UTF-8 é aceito,
  valores inválidos são corrigidos um a um e a gravação é atômica.
- Erros vão para `logs/neko.log` (rotativo) e `logs/crash.log`, com aviso ao usuário.
- A resposta do LLM roda fora da thread da interface, e o mascote anima enquanto pensa.
- Respostas inesperadas do LLM voltam ao modo básico, com aviso na resposta.
- Instância única com recuperação após queda.
- Conexões SQLite são fechadas a cada uso.
- A expressão sonolenta da pausa não se perde mais em um clique.
- Falha ao abrir o diário mostra onde o arquivo está.

### Windows e instalação

- Autostart pela chave `Run` do usuário, compatível com pastas acentuadas e sem janela de console.
  O `.bat` da v0.1 é removido automaticamente.
- Novo `install.bat`, de duplo clique, com verificação de versão e de 64 bits, venv limpo, atalho
  opcional e acentos corretos no PowerShell 5.1.
- Novo `uninstall.bat`, que mantém os dados salvo confirmação explícita.
- Novo `diagnostico.bat` e opção `--diagnostics`.
- Dependências com versão fixa e `PySide6-Essentials` no lugar do metapacote, reduzindo o `.venv`.
- `.gitignore` corrigido, agora cobrindo memórias, diário, configuração e logs.

### Correções no prompt do LLM

- Removido o `\n\n` literal.
- O histórico enviado sempre começa com o usuário.

### Testes

- Primeira suíte automatizada, em `tests/`, com `unittest`.

## 0.1.0

- Mascote flutuante, chat por regras, memória em Markdown, diário e observação opcional.
