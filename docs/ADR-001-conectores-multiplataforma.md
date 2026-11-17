# ADR-001: Conectores de redes sociais

**Status:** Aceito para implementação incremental

## Contexto

O Tufenor Video precisa concentrar várias redes em uma experiência única, mas
login, upload, permissões e limites são diferentes em cada plataforma. Não é
seguro fingir que uma sessão de navegador equivale a uma API de publicação.

## Decisão

O aplicativo terá um catálogo único de redes e dois níveis de integração:

1. **API oficial/OAuth:** quando a rede aprovar o aplicativo, o conector envia
   o vídeo e a descrição usando os escopos autorizados.
2. **Compartilhamento do Android:** quando não houver API aprovada, o app abre a
   rede oficial com o arquivo e a descrição para o usuário revisar e confirmar.

Os tokens de OAuth não ficam no código-fonte nem em arquivos compartilhados. A
implementação final deverá usar PKCE, armazenamento seguro e revogação local.

## Estado desta etapa

- Instagram: login local existente para leitura autorizada do perfil.
- TikTok, YouTube, Facebook, LinkedIn, X e WhatsApp: catálogo visual e abertura
  da rede; publicação via API ainda depende de cadastro, escopos e aprovação de
  cada fornecedor.
- A tela informa explicitamente quando está usando compartilhamento, para não
  apresentar uma abertura de login como uma conexão de API concluída.

## Próximas integrações

- TikTok Content Posting API com `video.publish` e auditoria do cliente.
- YouTube Data API com OAuth e `youtube.upload`.
- LinkedIn Posts/Videos API com `w_member_social` ou escopo de organização.
- Meta Graph API para contas e páginas elegíveis.

Cada conector será testado isoladamente, com limite de taxa, renovação de token,
cancelamento, logs sem segredos e um botão de desconectar.
