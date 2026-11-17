# Tufenor Video — experiência, anúncios e publicação

## Fluxo do usuário

1. Colar ou compartilhar o URL.
2. Confirmar que o conteúdo é próprio ou autorizado.
3. Tocar em **Analisar vídeos**.
4. Revisar a lista e usar **Selecionar todos** ou marcar itens individuais.
5. Opcionalmente importar um `.txt`: uma linha corresponde à descrição de um
   vídeo na ordem selecionada. A legenda padrão só é usada quando não houver
   linha correspondente.
6. Opcionalmente escolher uma imagem de marca-d'água e um dos quatro cantos.
7. Baixar. Os arquivos processados aparecem em `Filmes/Tufenor Video`.

## Anúncios

O APK de desenvolvimento usa os IDs de demonstração do Google Mobile Ads. Eles
devem permanecer durante os testes e ser trocados pelos IDs reais do AdMob
somente depois de registrar o aplicativo no AdMob.

Antes do lançamento, é necessário:

- configurar o App ID e o Banner Ad Unit ID reais;
- integrar e validar consentimento quando aplicável;
- publicar uma política de privacidade acessível dentro do app e na ficha;
- declarar **Contém anúncios** no Play Console;
- preencher a seção Segurança dos dados de acordo com o SDK de anúncios e a
  política publicada;
- testar o APK/AAB assinado em um dispositivo físico.

## Marca-d'água

O processamento usa Jetpack Media3 Transformer. A imagem é aplicada como
overlay com transparência de 86% e escala de 22%, em um dos cantos. Como há
reencodificação, o processamento pode consumir bateria e tempo; o app deve
mostrar progresso antes de liberar o vídeo para a galeria.

## Limites conhecidos

- O app não publica silenciosamente em segundo plano. A notificação abre o
  compartilhamento e o usuário confirma na rede social.
- Perfis privados ou bloqueados pela plataforma podem não fornecer uma lista.
- O texto original de um perfil só é usado quando o extrator o fornece; o
  arquivo `.txt` é o método determinístico para controlar descrições em lote.
