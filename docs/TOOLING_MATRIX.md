# Matriz de skills, plugins e ferramentas

Esta matriz evita instalar ferramentas por impulso. A regra é usar o que já
existe, adicionar um componente por vez e medir o ganho.

| Área | Skill aplicada | Plugin/integração | Ferramenta open source | Situação |
|---|---|---|---|---|
| Produto/CEO | `write-spec`, `roadmap-update` | Linear sugerido | Markdown + GitHub Issues | pronta localmente |
| UX/UI | `design-system`, `design-handoff`, `accessibility` | Figma sugerido; Canva conectado | Material 3 + Compose | UI instalada no A53 |
| Frontend Android | `architecture`, `documentation` | GitHub conectado | Gradle, Android SDK | ativo |
| Backend/conectores | `architecture`, `deploy-checklist` | GitHub | APIs oficiais + contratos | incremental |
| Dados | `testing-strategy` | PostHog sugerido | JSONL/manifestos locais | sem telemetria externa |
| QA funcional | `testing-strategy` | GitHub Actions | Maestro, se instalado | fluxo preparado |
| Qualidade Kotlin | `code-review` | GitHub Actions | detekt e ktlint | recomendação para próximo ciclo |
| Segurança | `security-scan`, `validation` | GitHub | OWASP Dependency-Check | recomendação, sem download automático |
| Operações | `runbook`, `process-optimization` | GitHub Actions | PowerShell + relatórios | ativo |
| Financeiro | `finance` | PostHog/planilha quando necessário | Billing do Google Play | depende da conta comercial |
| Publicação | `deploy-checklist` | GitHub | APK assinado e checklist | debug instalado; release pendente |

## Plugins sugeridos

- **Linear:** roadmap, tarefas, prioridades e dependências.
- **Figma:** telas, componentes, handoff e revisão visual.
- **PostHog:** eventos de produto, funil, erros e flags. Só conectar depois de
  definir quais eventos não contêm URL privada, legenda ou token.

GitHub e Canva já aparecem conectados. Linear, Figma e PostHog foram apenas
sugeridos; nenhuma conta foi conectada automaticamente.

## Ferramentas pesquisadas

- [Maestro](https://github.com/mobile-dev-inc/maestro): Apache-2.0, testes E2E
  por acessibilidade e adequado ao A53 físico.
- [detekt](https://github.com/detekt/detekt): análise estática de Kotlin e
  relatórios SARIF/HTML.
- [ktlint](https://github.com/ktlint/ktlint): formatação e lint Kotlin.
- [OWASP Dependency-Check Gradle](https://github.com/dependency-check/dependency-check-gradle):
  identificação de dependências com vulnerabilidades conhecidas.

## Referências de interface pesquisadas

- [Now in Android](https://github.com/android/nowinandroid): referência oficial
  de Compose, Material 3, arquitetura modular e temas adaptativos.
- [Compose Samples](https://github.com/android/compose-samples): exemplos
  oficiais de componentes, navegação, testes e layouts para telas maiores.
- [Adaptive Apps Samples](https://github.com/android/adaptive-apps-samples):
  padrões oficiais para navegação e adaptação de layout.

Essas referências foram usadas como princípios — Material 3, componentes
reutilizáveis, densidade controlada e adaptação — sem copiar identidade,
textos ou telas proprietárias.

## Critério para instalar

Só instalar um binário se o repositório oficial, licença, versão compatível,
checksum/assinatura e reversão estiverem documentados. Dependências Gradle
devem entrar primeiro em branch de teste e passar pelo build do A53. Não usar
scripts remotos do tipo `irm ... | iex`.
