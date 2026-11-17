# JARVIS — assistente de voz que opera o PC

> Briefing original (claude.ai, conversa "Jarvis placa controle PC", 21/10/2026).
> Decisões tomadas depois, que valem por cima deste texto, estão no fim.

Estou construindo um assistente pessoal de voz, em português, que roda no
Windows e controla o computador e uma placa ESP32. Quero que você continue esse
projeto. Leia primeiro o arquivo de status local — ele contém o histórico completo.

## O que já existe e funciona

- ambiente virtual Python do projeto
- **ESP32 na rede local**, MicroPython. Endpoints HTTP:
  `/status` (JSON: temperature, humidity, motion, led), `/led/on`, `/led/off`,
  `/led/auto`, `/acordar-pc` (Wake-on-LAN), `/dormir-pc`
- **Agente de energia do PC** em uma porta local configurável (`scripts/pc_agent.py`),
  autenticado por token (`agente/TOKEN.txt`), ações `/sleep`, `/shutdown`,
  `/cancel`. Sobe sozinho com o Windows.
- Sensores que funcionam: LED (GPIO4), DHT11 (GPIO6), PIR (GPIO7), LCD I2C 16x2
- pasta `jarvis/` — esboço do assistente (cerebro.py, ferramentas.py,
  voz.py, jarvis.py). **Pode reescrever à vontade**, é só ponto de partida.
- Testes em `tests/` — rode e mantenha verdes.

## O que quero

```
"Hey Jarvis" → detecta fim da fala → transcreve → decide → age no PC → responde falando
```

Com um **centro de comando** aberto na tela mostrando o sistema vivo.

### Stack (confirmado como estado da arte, use esse)

| Função | Biblioteca |
|---|---|
| Palavra de ativação | **openWakeWord** (modelo `hey_jarvis`) |
| Detectar fim da fala | **Silero VAD** — não use limiar de volume, é ruim |
| Fala → texto | **faster-whisper** (`small`, int8, language="pt") |
| Texto → voz | **Piper** com voz pt-BR — bem melhor que a voz do Windows |
| Cérebro | Ollama local **e** API, alternável por config |

### Cérebro: os dois caminhos

Implemente os dois atrás da mesma interface, escolhido em `config.json`:

1. **Ollama local** — grátis e privado
2. **API** (Anthropic ou OpenAI) — rápido e preciso

Antes de decidir o padrão, **cheque se tenho GPU dedicada** (`nvidia-smi` ou
`wmic path win32_VideoController get name`) e me diga o resultado. Sem GPU,
um modelo 7B na CPU demora 10-20s por resposta e erra a escolha de ferramenta
— nesse caso recomende a API e me explique o custo estimado.

### Ferramentas do agente

Comece com estas: hora/data, abrir programa ou site, pesquisar na web,
ler sensores da ESP32, ligar/desligar a luz, suspender o PC, acordar o PC.

**Regras:**
- **Nunca** crie uma ferramenta de "executar qualquer comando". Poder demais
  para um modelo que erra. Ferramentas específicas e limitadas.
- Ação que muda estado da máquina (suspender, desligar) **pede confirmação
  falada** antes de executar.
- Se o modelo responder fora do formato esperado, o JARVIS **diz que não
  entendeu** em vez de chutar uma ação. Errar calado num sistema que mexe no
  PC é pior que admitir dúvida.

## Interface — centro de comando

Servida pelo próprio JARVIS (FastAPI ou Flask) em `http://localhost:8080`,
aberta num monitor. Atualiza por WebSocket, não por polling.

### Layout

```
┌──────────────────────────────────────────────────────────┐
│ J.A.R.V.I.S.        data·hora     ● placa   ● cérebro    │
├──────────────┬──────────────────────────┬────────────────┤
│ AMBIENTE     │                          │ ATIVIDADE      │
│ temp  umid   │       [ NÚCLEO ]         │ log do que     │
│ movimento    │        animado           │ ele fez        │
│              │                          │                │
│ SISTEMA      │      estado atual        │ AÇÕES RÁPIDAS  │
│ ALERTAS      │      última fala         │                │
├──────────────┴──────────────────────────┴────────────────┤
│ [ barra de comando ]                              [mic]  │
└──────────────────────────────────────────────────────────┘
```

O **núcleo** (canvas/WebGL) reage ao estado: repouso, ouvindo, pensando,
executando, respondendo, erro. Cor e ritmo mudam. É a presença viva do sistema
— o único elemento que se move.

### Direção visual: cyberpunk industrial

Pense **painel de controle industrial**, não pôster synthwave. Blade Runner
2049 e Ghost in the Shell, não capa de álbum neon.

- Base quase preta com viés frio. **Um** acento só (ciano ou verde-ácido),
  usado com economia — se tudo brilha, nada se destaca.
- Cores semânticas separadas do acento: âmbar = atenção, vermelho = crítico.
- Monoespaçada para **todo** dado numérico, com `tabular-nums`. Sans
  condensada para rótulos, em caixa alta com `letter-spacing`.
- Linhas de 1px, cantos retos. Nada de card arredondado com sombra em tudo.
- Textura sutil de scanline ou ruído, bem baixa opacidade.
- Densidade alta é bem-vinda — é um painel de operação, não uma landing page.

**Evite** (são clichês de interface gerada por IA): gradiente roxo-azul,
fonte Orbitron, glow em todo elemento, emoji como ícone, tudo centralizado,
`border-radius` uniforme, glassmorphism.

### UX — a parte que não pode falhar

- Estado visível **na forma**, não só na cor (quem não distingue cor precisa
  entender igual).
- Cada ação dá retorno em menos de 100ms, mesmo que seja só o núcleo mudando.
- Nada de spinner infinito: se o cérebro demora, mostre o que está fazendo.
- Funciona no celular (mesma rede). Colunas empilham, núcleo no topo.
- Teclado: foco visível, Enter envia, Esc cancela escuta.
- Respeite `prefers-reduced-motion` — desligue a animação do núcleo.

## Ordem de trabalho

Entregue funcionando em etapas, não tudo de uma vez:

1. **Servidor + interface** com dados reais da ESP32 e estado simulado do
   agente. Já dá pra ver e julgar.
2. **Cérebro + ferramentas**, testável por texto (sem microfone ainda).
3. **Voz**: wake word → VAD → Whisper → Piper, ligado ao resto.
4. **Polimento**: sobe com o Windows, trata queda de rede, reconecta sozinho.

Pare ao fim de cada etapa e me mostre. Não construa tudo antes de eu ver nada.

## Armadilhas já descobertas neste projeto

Custaram horas. Não repita:

- **Arquivos `.bat`:** nunca use blocos entre parênteses (`if ... ( ... )`).
  Quebram. Use `goto` e rótulos. Sempre salve com quebra de linha CRLF.
- **ESP32-S3 some do USB ao resetar.** Depois de `mpremote reset`, espere a
  porta COM reaparecer antes de abrir — senão dá "dispositivo inexistente".
- **I2C do LCD:** use `SoftI2C` a 100 kHz. O periférico de hardware a 10 kHz
  devolve `ENODEV` nesta placa.
- **Não varra pinos GPIO em massa** procurando dispositivo — reinicia a placa
  e trava o USB.
- O pino **5V da ESP32 não entrega corrente** nesta placa. Periféricos de 5V
  vêm de fonte externa, com GND comum.

## Como quero que você trabalhe

- Português nos comentários, nos nomes de variável e na interface.
- Comentário explica **por que**, não o que o código já diz.
- Teste antes de dizer que funciona. Se não testou, diga que não testou.
- Se algo meu estiver errado, me corrija — não implemente em silêncio.
- Pergunte antes de assumir, quando a escolha mudar a arquitetura.

---

## Decisões tomadas depois (21/10/2026)

- **Núcleo em ciano**, um acento só. O fogo laranja do vídeo fica de fora.
- **Cada estado é uma forma diferente**, não só uma cor:

  | Estado | Forma |
  |---|---|
  | repouso | anel fino, girando devagar |
  | ouvindo | anel + feixe vertical, pulsando com o volume do mic |
  | pensando | esfera de partículas densa, girando rápido |
  | executando | partículas alinhando-se em raios |
  | respondendo | anel ondulando no ritmo da voz |
  | erro | forma fragmentada e parada, em vermelho |

- **Fora do escopo por enquanto:** o escritório 3D com agentes do vídeo.
- **Stream Deck:** perguntar se o usuário tem um antes da etapa 4.
- **GPU:** GTX 1060 Max-Q 6 GB (≈5 GB livres). O cérebro padrão é a API com
  **Claude Haiku 5.5** (`claude-haiku-5-5`); a GPU fica para o faster-whisper.
  Ollama continua como alternativa no `config.json`.
- **Chave da API:** variável de ambiente `ANTHROPIC_API_KEY`, nunca em arquivo.
- **openWakeWord no Windows:** `inference_framework="onnx"` (tflite não existe
  no Windows). `hey_jarvis` é treinado em inglês — se falhar com sotaque,
  ajustar o limiar antes de pensar em treinar modelo próprio.
- O esboço antigo (`jarvis\`, `voice\`, `ui\`) foi para `_lixeira\`.
