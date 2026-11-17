# JARVIS Companion — app Android nativo

Aplicativo nativo em Kotlin + Jetpack Compose para controlar o JARVIS a
partir do Galaxy A53 (e qualquer Android 7+). Conversa diretamente com o
backend FastAPI já existente em `jarvis/servidor.py` pelas rotas
`/login`, `/api/comando`, `/api/escutar`, `/api/cancelar`, `/api/presenca`,
`/api/presencas`, `/api/saude` e `/ws`. **Não é WebView** — o painel web
continua existindo em `/mobile` como alternativa.

## Características

- **UI nativa**: Material 3 escuro cyberpunk sóbrio, ciano/magenta sobre
  preto profundo, contraste AA, fontes escaláveis até 200%.
- **Rede**: OkHttp + kotlinx-serialization, mesmo cliente para REST e
  WebSocket, backoff exponencial, nunca abre conexão duplicada.
- **Segurança**: sessão guardada em `EncryptedSharedPreferences` (chave
  mestre no Android Keystore), TLS validado pela plataforma, cleartext só
  nos hosts da rede local em build de debug.
- **Privacidade**: localização apenas sob demanda, pedida pelo botão
  "verificar agora". O servidor arredonda a coordenada; o telefone nunca
  grava sua posição exata.
- **Resiliência**: estados visuais claros (ONLINE, RECONECTANDO, OFFLINE,
  AGUARDANDO LOGIN, ERRO), ping manual na tela de diagnóstico.
- **Modo econômico**: chave em Configurações, pensada para reduzir updates
  no futuro (gancho pronto, consumo atual já é baixo).

## Como compilar

### Pré-requisitos (uma vez)

1. **Android Studio Rabbit 2** ou mais novo — já está instalado em
   `C:\Program Files\Android\Android Studio\`.
2. **Android SDK** — o Studio baixa automaticamente no primeiro sync
   (~5 GB).
3. JDK 17+ — o Studio já traz o `jbr` dele (JDK 25).

Nada mais precisa estar no PATH do Windows; o Studio orquestra tudo.

### Passos no Android Studio

1. Abrir Android Studio → **Open** → selecionar `mobile-android`.
2. Esperar o Gradle Sync. Na primeira vez o Studio vai perguntar se pode
   instalar os componentes do SDK — aceitar.
3. Em **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
4. O APK de debug sai em
   `app/build/outputs/apk/debug/app-debug.apk`.

Para release assinado, criar um keystore próprio em
`~/.gradle/jarvis-release.jks` e configurar as propriedades `storeFile`,
`storePassword`, `keyAlias`, `keyPassword` num `signingConfigs` adicional em
`app/build.gradle.kts`. Não comitar o keystore ou as senhas.

### Linha de comando (opcional)

Depois do primeiro sync pelo Studio, o próprio Studio escreve o
`gradle-wrapper.jar` e as variáveis de ambiente. A partir daí dá para:

```sh
cd mobile-android
.\gradlew.bat assembleDebug
.\gradlew.bat test
.\gradlew.bat connectedAndroidTest   # precisa de dispositivo ou emulador
```

## Como instalar no A53

1. Conecte o A53 via USB e habilite **Depuração USB** nas Opções do
   desenvolvedor.
2. No Android Studio: **Run → Run 'app'**, escolha o A53 na lista.
   O app sobe como `JARVIS Companion (debug)`.
3. Alternativa: copie `app-debug.apk` para o celular e abra para instalar
   (a Play Protect vai pedir confirmação por ser instalação de origem
   desconhecida).

## Primeira configuração dentro do app

1. Abra o app. Como ainda não há URL configurada, ele vai direto para
   **Configurações**.
2. Digite o endereço do seu JARVIS — por exemplo
   `http://192.168.50.10:8080` em casa, ou a URL do seu túnel seguro fora.
3. Salve. O app volta para o **Login**.
4. Digite a senha do painel. O cookie vai ser guardado cifrado no
   Keystore; da próxima vez você entra direto.

## Permissões

- **Internet** (sempre): falar com o JARVIS.
- **Localização aproximada** (sob demanda): só quando você aperta
  "verificar agora". A permissão pode ser revogada pelas Configurações do
  Android a qualquer momento.

## Testes

- Unitários (JVM, sem dispositivo): `./gradlew test`
  - `DtosTest`: tolerância a campos novos vindos do JARVIS.
  - `CookieJarTest`: persistência e expiração de sessão.
  - `SettingsStoreTest`: normalização de URL.
- Instrumentado (precisa Android ou emulador): `./gradlew connectedAndroidTest`
  - `MainScreenUiTest`: tela de login desenha os elementos principais.

## Limites conhecidos

- Não encaminha áudio contínuo do microfone do celular para o PC — isso
  continua sendo papel do satélite Termux descrito em `docs/A53.md`.
- Sem notificações push ainda (o canal WebSocket serve o celular enquanto
  o app está em foco; para alertas em background, próxima iteração traz
  um `ForegroundService`).

## O que NÃO foi feito e por quê

- **APK não foi compilado automaticamente**: este PC ainda não tem o
  Android SDK baixado. O projeto está pronto para build assim que o Studio
  completar o primeiro sync. Nenhum arquivo dessa compilação está em
  commit; nenhum SHA-256 foi forjado.
- Nenhum segredo, token ou chave foi incorporado ao projeto.
