# Arquitetura multi-rede do Tufenor Video

## Objetivo

Administrar várias empresas, perfis e contas sociais em uma fila única, sem
tratar uma rede como se todas tivessem as mesmas permissões.

## Redes previstas

Instagram, TikTok, Facebook, YouTube, LinkedIn, X e WhatsApp entram no mesmo
modelo de conta. Cada conector informa o que realmente consegue fazer:

- `DIRECT_API`: publica pela API oficial;
- `DRAFT_API`: envia como rascunho para revisão;
- `ASSISTED_SHARE`: prepara o vídeo e abre o aplicativo da rede para confirmação;
- `NOT_CONFIGURED`: conta ainda não vinculada ou OAuth incompleto.

## Fluxo

1. A conta principal autentica o administrador.
2. O administrador cria uma agência ou cliente.
3. O cliente autoriza cada conta social individualmente.
4. O app registra a conta, o perfil e o modo disponível.
5. Vídeo, legenda, hashtags e marca-d'água viram um `PublicationJob`.
6. O agendador distribui os jobs de hora em hora.
7. O roteador envia cada job ao conector correto.
8. O histórico grava `PUBLISHED`, `FAILED`, `PAUSED_BY_PLATFORM_LIMIT` ou
   `WAITING_USER_CONFIRMATION`.

## Segurança e limites

- Senhas nunca são armazenadas pelo app.
- Tokens devem ficar criptografados e ser revogáveis por conta.
- O Premium remove o limite interno do lote, mas não ignora limites das redes.
- Publicação direta só é liberada após OAuth, permissões e requisitos da rede.
- Sem API autorizada, o app usa compartilhamento assistido; não simula CAPTCHA,
  não tenta burlar autenticação e não clica escondido em outro aplicativo.

## Estado atual

O Android já tem a fila horária local, o limite Free/Premium e o modo de
compartilhamento. Este documento e `MultiNetworkPublication.kt` criam o
contrato comum para os conectores. OAuth, backend de tokens e publicação direta
por rede ainda precisam ser configurados e testados separadamente.
