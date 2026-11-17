# Componentes open source selecionados para o JARVIS

Este documento registra as referências pesquisadas e como elas serão adaptadas. Não fazemos `git clone` nem executamos código de terceiros automaticamente: cada componente passa por revisão, licença, dependências e teste isolado.

## Seleção inicial

### 1. MicroPython oficial para ESP32-S3

- Fonte: https://github.com/micropython/micropython
- Uso no JARVIS: firmware dos sensores e atuadores.
- Estado: ativo na ESP32-S3 N16R8 com a variante `ESP32_GENERIC_S3-SPIRAM_OCT`.

### 2. openWakeWord

- Fonte: https://github.com/dscripka/openWakeWord
- Uso planejado: detecção local de “Jarvis” no PC, sem enviar áudio contínuo para a nuvem.
- Adaptação: módulo isolado `jarvis/voice/wakeword`, com sensibilidade, cooldown e teste de falso positivo.
- Decisão: não rodar o modelo diretamente na ESP32 nesta primeira fase; a ESP32 ficará como dispositivo físico.

### 3. faster-whisper

- Fonte: https://github.com/SYSTRAN/faster-whisper
- Uso planejado: speech-to-text local em português brasileiro.
- Adaptação: modelos `tiny`, `base` e `small` configuráveis; CPU como padrão e GPU opcional.

### 4. Piper TTS

- Fonte: https://github.com/rhasspy/piper
- Uso planejado: resposta de voz local, com voz masculina brasileira quando o modelo compatível estiver disponível.
- Adaptação: interface `jarvis/voice/tts` para trocar a voz sem alterar o roteador de comandos.

### 5. Rhasspy / Wyoming

- Fontes: https://github.com/rhasspy/rhasspy3 e https://github.com/rhasspy/wyoming
- Uso planejado: referência de protocolo para separar microfone, wake word, STT, intenção e TTS.
- Adaptação: JARVIS manterá sua própria política de segurança e executor; não será dependente do Home Assistant.

### 6. ESP32 como cliente de áudio

- Referências: https://github.com/CapitanaIcoachai/local-voice-edge e https://github.com/kamilamgad/ESP32-Live-Voice-Assistant
- Uso planejado: referência para futura comunicação Wi-Fi entre a placa e o JARVIS no PC.
- Decisão: não copiar scripts de rede ou credenciais; primeiro testar sensores e atuadores localmente.

### 7. OpenVoiceOS

- Fonte: https://github.com/OpenVoiceOS/OpenVoiceOS
- Uso planejado: estudar o conceito de skills/plugins e ciclo de intents.
- Decisão: não instalar o conjunto completo agora porque é pesado para a primeira versão e duplicaria o roteador próprio do JARVIS.

### 8. Painel local para iPhone: página web servida pela ESP32

- Referência de interface/arquitetura: [Home Assistant Core](https://github.com/home-assistant/core), projeto local-first Apache-2.0; o [app oficial Home Assistant para iOS](https://github.com/home-assistant/iOS) também é Apache-2.0.
- Uso no JARVIS: referência para o controle no iPhone e a separação entre sensores, estado e comandos.
- Decisão para este protótipo: não instalar Home Assistant agora. Ele precisaria de um servidor sempre ligado, e a ESP32 atual usa MicroPython próprio, não uma integração Home Assistant pronta. O painel leve será servido pela própria ESP32 e aberto no Safari; isso é gratuito, funciona também no navegador do PC e não exige app da App Store.
- Limite: o painel controla somente as rotas explicitamente implementadas no firmware. Não é o cérebro/assistente de voz nem substitui uma API do JARVIS no Windows.

### 9. Repositório Personal Jarvis como referência de software de PC

- Fonte: [PersonalJarvis/PersonalJarvis](https://github.com/PersonalJarvis/PersonalJarvis), Apache-2.0, aplicação para desktop Windows/macOS/Linux com modo servidor/browser.
- Ponto útil: separa interface, voz, agentes, integrações e política de aprovação; divulga opções locais como Ollama e fala local.
- Custo real: o software é aberto/gratuito, mas a IA de conversa pode exigir hardware para rodar modelo local; usar provedores hospedados pode custar dinheiro. Recursos remotos de voz também podem exigir HTTPS.
- Decisão: usar como referência e não executar o instalador nem substituir este firmware/projeto automaticamente. Não é plug-and-play para os sensores MicroPython já montados; a conexão teria de ser implementada e validada.

### Critério para opções “grátis”

“Grátis” aqui significa código aberto e execução local sem mensalidade obrigatória; ainda pode haver custo de eletricidade, hardware, modelos hospedados ou serviços externos. Para a necessidade imediata, o painel servido pela ESP32 é a opção mais simples. Home Assistant é melhor como plataforma ampla de automação se houver um host sempre ligado. Personal Jarvis é uma referência para o lado do assistente no PC, não um controle mágico da ESP32.

## Adaptação para plugins do JARVIS

Cada integração futura deve expor:

```python
class JarvisPlugin:
    name = "nome_do_plugin"

    def health(self) -> dict:
        ...

    def handle(self, intent: dict) -> dict:
        ...
```

Regras mínimas:

1. Nenhum plugin recebe shell irrestrito.
2. Ações destrutivas exigem confirmação explícita.
3. O plugin deve funcionar sem internet quando tecnicamente possível.
4. O plugin deve registrar saúde, versão e dependências.
5. A instalação de qualquer dependência fica confinada ao ambiente virtual `.venv` do projeto.

## Próxima implementação

1. Finalizar o teste do LED/buzzer na ESP32.
2. Criar o esqueleto `jarvis/voice` no PC.
3. Adicionar STT local e TTS local atrás de interfaces estáveis.
4. Adicionar wake word local.
5. Criar o transporte Wi-Fi autenticado entre PC e ESP32.
