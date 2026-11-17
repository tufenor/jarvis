# Plano — A53 Experience

**Status:** Proposto  
**Data:** 2026-11-14  
**Alvo:** Samsung Galaxy A53 5G SM-A536E, Android 16  
**Princípio:** experiência inspirada em simplicidade e fluidez de produtos premium, sem copiar marcas, sem root na primeira fase e sem modificar firmware.

## Objetivo

Criar uma camada de experiência Android com aparência limpa, animações controladas,
interações consistentes e desempenho medido. O projeto não promete transformar o
Android em iOS nem reescrever a One UI por meio de um APK.

## Limites técnicos

### Fase segura — sem root

- launcher próprio opcional, reversível e desinstalável;
- grade, ícones, widgets e gestos próprios;
- tema claro/escuro, tipografia, espaçamento e componentes consistentes;
- tela de controle para recursos do JARVIS e da câmera;
- animações curtas, previsíveis e com redução de movimento;
- Baseline Profile, R8, redução de inicializações e otimização de memória;
- uso de `WorkManager` para tarefas não urgentes;
- telemetria local de frames, memória, bateria e temperatura, sem enviar dados pessoais.

### Fase avançada — somente após aprovação

- overlays do sistema;
- alterações de SystemUI;
- kernel, HAL, bibliotecas proprietárias ou ROM;
- bootloader desbloqueado/root.

Essa fase pode afetar Knox, OTA, câmera, segurança e garantia. Não será iniciada
automaticamente.

## Direção visual

- superfícies limpas, contraste alto e hierarquia tipográfica clara;
- cantos e sombras usados com moderação, sem excesso de cartões ou gradientes;
- gestos com retorno visual e háptico quando suportado;
- estados completos: carregando, vazio, erro, sucesso, permissão e offline;
- acessibilidade: tamanho de fonte, contraste, TalkBack, foco e redução de movimento;
- componentes próprios, sem copiar layout, ícones ou identidade proprietária da Apple.

## Arquitetura de trabalho

1. **Auditoria:** medir versão, resolução, densidade, memória, frames, consumo e permissões.
2. **Design system:** tokens de cor, tipografia, espaçamento, elevação, movimento e ícones.
3. **Shell opcional:** launcher e painel A53 Experience, sem substituir a One UI permanentemente.
4. **Integração:** câmera, JARVIS e atalhos do sistema somente por APIs permitidas.
5. **Desempenho:** Baseline Profile, Macrobenchmark e testes em aparelho real.
6. **Validação:** comparar abertura, rolagem, retorno ao app, aquecimento e autonomia.
7. **Rollback:** desativar launcher, remover APK e restaurar preferências anteriores.

## Papéis no protocolo compartilhado

Em vez de criar vários chats independentes, o projeto usa papéis registrados em
um único plano:

- Produto: define o que deve melhorar;
- UX/UI: desenha fluxos e estados;
- Android: implementa componentes e APIs;
- Desempenho: mede frames, memória e bateria;
- Segurança: impede root, permissões excessivas e coleta indevida;
- QA: testa no A53 e registra regressões;
- Release: gera APK instalável, versão e rollback.

Cada decisão deve registrar hipótese, evidência, alteração e reversão.

## Critérios de sucesso da primeira fase

- APK instalável e removível sem root;
- One UI continua intacta;
- nenhuma proteção térmica ou de segurança alterada;
- ausência de crash no fluxo principal;
- navegação responsiva em 60 Hz quando o aparelho permitir;
- testes em 320 dp, 411 dp e orientação paisagem;
- comparação antes/depois com métricas, não apenas impressão visual.

## Próximo passo

Executar auditoria somente leitura via ADB e inspecionar o módulo Android existente
antes de criar launcher ou alterar a tela principal. O resultado deve definir se
a primeira entrega será um painel do JARVIS, um launcher opcional ou apenas uma
biblioteca visual reutilizável.
