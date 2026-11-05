# Segurança

O Neku lê a tela e mexe em arquivos, então levamos falhas de segurança a sério.

## Como relatar

Não publique detalhes de uma falha em uma issue aberta. Abra uma issue dizendo apenas que precisa de um canal privado, e combinamos a partir daí.

Ajuda muito incluir a versão, os passos para reproduzir e o impacto.

## O que conta como falha

- Dados da tela, memórias ou conversas saindo do computador.
- Janela privada ou dado sensível passando pelo filtro de forma reproduzível.
- Texto da tela ou de memórias acionando ações ou mudando regras do programa.
- Ação executada sem a confirmação exigida, ou fora das pastas pessoais.
- Execução de comandos fora do catálogo de ações.

## O que o Neku não protege

- O diário em `data/tela/` é texto simples. Outros programas rodando na sua conta conseguem ler esse arquivo.
- O filtro de privacidade usa listas e padrões e pode falhar. Veja a seção de privacidade do [README](README.md).
- As respostas do modelo local podem estar erradas.

Se você suspeita que o seu computador está comprometido, deixe a visão desligada até resolver.
