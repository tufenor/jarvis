# Pacote de verificação para o ChatGPT

Este projeto Android nativo foi escrito pelo Claude e **não foi compilado
ainda** — este PC não tem o Android SDK baixado. O Android Studio Rabbit 2
está instalado em `C:\Program Files\Android\Android Studio\` e traz o JDK 25
embutido (`jbr/`).

Sua tarefa, ChatGPT, é verificar que o projeto compila, passa nos testes e
instala no Galaxy A53. Siga os passos abaixo na ordem e me devolva o retorno
de cada um.

## 0. Antes de começar

- Caminho do projeto: `mobile-android`
- Nada precisa estar no PATH — o Android Studio orquestra Gradle + SDK.
- Backend FastAPI continua intocado (os 284 testes Python verdes).

## 1. Primeiro sync no Android Studio

1. Abrir Android Studio → **File → Open** → `mobile-android`.
2. Aceitar instalar os componentes do SDK que o Studio pedir (platform 34,
   build-tools, platform-tools). Download inicial ~5 GB.
3. Aguardar o Gradle Sync terminar sem erros.

**Devolver:** cópia do painel "Build Output" do sync, ou confirmação "BUILD
SUCCESSFUL".

## 2. Testes JVM

No terminal do Android Studio (ou `.\gradlew.bat` depois do sync):

```bat
cd mobile-android
.\gradlew.bat test
```

Esperado: 3 classes verdes (`DtosTest`, `CookieJarTest`, `SettingsStoreTest`).

**Devolver:** saída completa do `test` e o caminho dos relatórios em
`app\build\reports\tests\`.

## 3. Lint

```bat
.\gradlew.bat lint
```

**Devolver:** resumo dos erros/warnings e o relatório em
`app\build\reports\lint-results-debug.html`.

## 4. APK de debug

```bat
.\gradlew.bat assembleDebug
```

**Devolver:**

- SHA-256 do arquivo:
  ```powershell
  Get-FileHash mobile-android\app\build\outputs\apk\debug\app-debug.apk -Algorithm SHA256
  ```
- Tamanho do APK em MB.
- Confirmação de que o path existe.

## 5. Teste instrumentado (opcional, precisa de dispositivo ou emulador)

Com o A53 conectado por USB com Depuração USB ativa, ou com um emulador aberto:

```bat
.\gradlew.bat connectedAndroidTest
```

Esperado: `MainScreenUiTest` verde.

**Devolver:** saída e, se houver, o relatório em
`app\build\reports\androidTests\connected\`.

## 6. Instalação real no Galaxy A53

1. A53 conectado por USB, Depuração USB ligada.
2. No Android Studio: **Run → Run 'app'** → escolher o A53.
3. No celular: abrir o app `JARVIS Companion (debug)`.
4. Preencher a URL do JARVIS (ex.: `http://192.168.50.10:8080`).
5. Fazer login com a senha do painel.
6. Testar os botões: ENVIAR (texto), ESCUTAR, CANCELAR, VERIFICAR AGORA
   (localização).

**Devolver:** screenshot ou vídeo curto mostrando o app funcionando, e qualquer
comportamento estranho.

## 7. Bloqueios esperados que NÃO são falha

- Primeiro sync pode pedir aceitar licenças do SDK (`sdkmanager --licenses`).
  Aceitar.
- Gradle vai baixar várias dependências do Maven central na primeira vez.
  Rede lenta pode levar vários minutos.
- `connectedAndroidTest` falha sem dispositivo/emulador — isto é esperado.

## 8. O que NÃO fazer

- Não alterar nenhum arquivo do backend FastAPI (`jarvis/**`,
  `tests/**`, `scripts/**`, `firmware/**`).
- Não gerar keystore de release antes que o usuário peça.
- Não comitar APKs nem keystores.
- Não logar nem imprimir senhas, tokens ou cookies.

## Resultado final que eu espero

Um bloco curto:

```
SYNC:       OK | FAIL (motivo)
TEST:       3 verdes / N vermelhos
LINT:       X errors / Y warnings
APK DEBUG:  app-debug.apk (SHA-256: ...) tamanho: XX,X MB
INSTRUMENTADO: OK | NAO RODADO (motivo)
A53 INSTALADO: OK (print) | NAO
```

Depois disso eu (Claude) corrijo o que vier com defeito.
