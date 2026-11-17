# ADR-002: Plataforma modular de captura e publicação

**Status:** Aceita para evolução incremental  
**Data:** 2026-11-11  
**Decisores:** Tufenor e equipe do projeto

## Contexto

O aplicativo começou como um downloader em uma tela única e passou a incluir
perfis, descrições, marca-d’água, fila e conectores. Crescer sem separar essas
responsabilidades aumenta o risco de duplicar publicações, perder legendas e
misturar contas.

## Decisão

Adotar quatro domínios no produto: **Studio**, **Biblioteca**, **Agenda** e
**Contas**. O Android continua local-first; cada conector de rede é opcional,
isolado por perfil e só usa API oficial ou compartilhamento assistido.

## Alternativas

| Opção | Vantagem | Risco |
|---|---|---|
| Uma tela com todas as funções | rápida no protótipo | difícil de testar e entender |
| Separar por domínios no Android | simples para o usuário e testável | requer migração gradual da UI |
| Backend central obrigatório | facilita agendamento remoto | custo, tokens e privacidade maiores |

Foi escolhida a segunda opção. Um backend pode ser adicionado depois para
contas empresariais, sem obrigar o usuário local a enviar mídia ou tokens.

## Consequências

- Fila e histórico ganham contratos próprios.
- A interface pode mostrar capacidade real por rede.
- OAuth e tokens nunca ficam misturados com o download.
- Será necessário manter testes de migração e compatibilidade entre versões.

## Plano de migração

1. Consolidar tokens visuais e componentes de estado.
2. Extrair Biblioteca e Agenda para telas/rotas independentes.
3. Criar contratos de conector e idempotência.
4. Adicionar testes instrumentados no A53.
5. Só então ativar novos conectores em produção.
