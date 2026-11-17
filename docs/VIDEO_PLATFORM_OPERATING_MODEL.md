# Tufenor Video — modelo operacional do produto

## Objetivo

Transformar o aplicativo em uma plataforma de operação de conteúdo: importar
um URL, revisar os itens encontrados, preservar a descrição, preparar mídia,
organizar por perfil e publicar ou agendar somente quando a rede oferecer uma
integração autorizada.

## Áreas responsáveis

| Área | Responsabilidade | Evidência de saída |
|---|---|---|
| Produto/CEO | Prioridade, limites do plano e decisões de risco | roadmap e decisão registrada |
| UX/UI | Fluxo simples, linguagem clara, acessibilidade e estados de erro | protótipo e checklist visual |
| Frontend Android | telas, estados, navegação, fila e feedback | APK testável no A53 |
| Backend/integrações | APIs oficiais, OAuth, retries e idempotência | contrato e teste de integração |
| Engenharia de dados | metadados, descrições, histórico e auditoria | esquema versionado e relatório |
| Segurança/privacidade | tokens cifrados, escopo mínimo e remoção segura | revisão sem segredos no Git |
| QA | testes unitários, integração, smoke e regressão | relatório diário e quinzenal |
| Operações | monitoramento, atualização de extratores e rollback | runbook executável |
| Financeiro | Premium, anúncios, custos de infraestrutura e limites | decisão de custo documentada |
| Conteúdo | direitos, marca-d’água, legenda e calendário | confirmação do usuário |

## Arquitetura alvo

```text
Android
  Studio -> análise -> seleção -> preparação -> fila -> resultado
  Perfis -> contas isoladas por perfil
  Biblioteca -> arquivos, descrições e histórico
  Contas -> OAuth/API oficial ou compartilhamento assistido

Serviços
  downloader -> metadata/descrição -> armazenamento local
  scheduler -> fila idempotente -> conector da rede
  observability -> eventos sem tokens -> diagnóstico

Governança
  teste diário -> relatório
  auditoria de 14 dias -> integridade, segurança e dados completos
```

## Regras de produto

1. O usuário fornece o URL e pode revisar a lista antes de baixar.
2. Descrição original, descrição importada e descrição editada são campos
   diferentes; nunca sobrescrever silenciosamente.
3. Cada item possui identidade estável, perfil, rede, horário e estado.
4. O job pode ser repetido sem duplicar download ou publicação.
5. A publicação direta exige conexão oficial e permissão válida. Sem isso, o
   app abre o compartilhamento assistido e informa a limitação.
6. Nunca apagar o original automaticamente. A exclusão só ocorre após uma
   confirmação explícita e fica registrada no histórico.
7. Token, cookie e identificador privado não entram em logs, screenshots,
   commits ou relatórios.

## Estados obrigatórios da fila

`RASCUNHO -> ANALISANDO -> SELECIONADO -> BAIXANDO -> PREPARADO -> AGENDADO ->
PUBLICANDO -> PUBLICADO`.

Estados de exceção: `BLOQUEADO_DIREITOS`, `ERRO_REDE`, `ERRO_MIDIA`,
`AGUARDANDO_LOGIN`, `CANCELADO`. Cada erro deve orientar a ação seguinte e
permitir tentar novamente sem perder a descrição.

## Cadência de qualidade

- **Diária:** compilar, testes unitários, análise de URLs de fixture, abertura
  do app, criação de perfil, fila vazia e tratamento de erro.
- **A cada 14 dias:** executar os testes diários e revisar todos os módulos,
  migrações de dados, permissões, arquivos grandes, segredos, filas órfãs,
  compatibilidade do A53 e regressão visual.
- **Após qualquer conector:** testar primeiro em conta de teste e registrar o
  ID de publicação; não considerar o conector pronto apenas por compilar.

## Critério de pronto

Uma melhoria só é considerada entregue quando tem código, teste, estado de
erro, reversão documentada, evidência no dispositivo quando for Android e
registro em `PROJECT_STATUS.md`.
