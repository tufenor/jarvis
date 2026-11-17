Estou construindo o JARVIS, um assistente de voz em português que roda no
Windows e opera um PC e uma placa ESP32-S3. Quem escreve o código é
o Claude Code (ou o Codex) direto na minha máquina; você não vê os arquivos,
então trabalhe só com o que está aqui e me peça o conteúdo de um arquivo quando
precisar.

O QUE JÁ FUNCIONA (atualizado em 21/10/2026)
- Aplicativo de janela (pywebview) com "centro de comando": painel industrial
  escuro, um acento ciano, núcleo animado que muda de FORMA por estado
  (repouso = anel; ouvindo = anel + feixe; pensando = esfera de partículas;
  executando = raios; respondendo = anel ondulando; erro = anel partido vermelho).
- Microfone sempre aberto: Silero VAD + faster-whisper "small" na GPU
  (GTX 1060 6 GB, int8, ~0,3–0,5 s por frase). Só reage quando ouve "Jarvis".
  "Jarvis, abre o Google" numa frase só funciona.
- Conversa contínua: depois do primeiro "Jarvis" o microfone segue valendo sem
  repetir o nome (30 s de silêncio fecham; "obrigado/tchau" encerra).
- Interrupção: se eu falo por cima, ele para de falar na hora. Detecta pela
  energia do microfone contra o eco esperado (ele sabe o que está tocando).
  Impressão de voz NÃO serve para isso (medido: voz dele 0,71–0,81 de
  semelhança com ela mesma, vozes de outros 0,59–0,81). Sem fone, voz fraca ou
  longe pode não interromper.
- Reconhece quem fala: "Jarvis, aprende minha voz" (pergunta o nome, pede 3
  frases), "esquece minha voz", "quem sou eu?". Só a impressão (256 números) é
  guardada, nunca o áudio. O modelo recebe "[Nome] pedido".
- Cérebro: Claude Haiku 5.5 pela API (testado: 8 de 8 pedidos certos, 1–8 s);
  alternativa local: Ollama qwen3.5:4b (fraco, 65 s na primeira carga).
- Ferramentas (lista fechada, sem "executar comando livre"): hora/data, abrir
  programa da lista, abrir site (só http/https), pesquisar no Google, ler
  sensores da placa, acordar PC, suspender PC (só com "sim" falado), mudar a
  janela de monitor.
- Janela fica no monitor 2 em repouso, vem pro 1 quando chamo; "muda de tela"
  e "chega pra lá" trocam na hora (sem consultar o cérebro).
- Voz: Piper pt-BR (faber) com leve efeito "de IA". Quero o estilo do JARVIS
  dublado pelo Eduardo Borgerth, mas SEM clonar a voz dele (direito de
  personalidade) — só vozes de licença aberta. Ainda vou escolher entre
  faber, cadu e jeff.
- ESP32 no Wi-Fi com só DHT11 (temperatura/umidade) e PIR
  (movimento); a luz foi desligada. Às vezes o servidor HTTP dela para de
  responder (causa não investigada).
- Agente de energia no PC (porta 8765, token) para suspender; Wake-on-LAN pela placa.
- 101 testes automáticos passando.

NÃO TESTADO COM GENTE DE VERDADE
- O cadastro de voz de ponta a ponta, a precisão com duas pessoas reais e a
  interrupção com a minha voz (só simulei digitalmente sobre eco gravado).

REGRAS DO PROJETO
- Ferramentas gratuitas/open source do GitHub, rodando local; nada pago sem avisar.
- Nada de ferramenta que roda comando arbitrário; ações que mudam a máquina
  pedem confirmação; resposta fora do formato = "não entendi", nunca chute.
- Segredos (chave da API, token) nunca em código, chat ou git.
- Teste antes de dizer que funciona; se não testou, dizer.

O QUE ESTOU PENSANDO AGORA: SISTEMA DE SKILLS "COMO A ALEXA"
Quero um esquema de skills. Proposta já discutida:
- Pasta por skill: skills/<nome>/ com skill.json (nome, descrição, ferramentas,
  se é perigosa, quem pode usar por voz) e skill.py. O JARVIS descobre sozinho;
  ligo/desligo por voz ou pelo painel.
- Rotinas ("bom dia" dispara uma sequência), alarmes, timers e lembretes que
  avisam por voz sem eu chamar.
- Skills iniciais: timers/alarmes, clima (Open-Meteo, gratuito), lista de
  compras e notas, mídia e volume do PC, agenda, notícias por RSS.
- Casa inteligente por Home Assistant (gratuito) ou direto pelas ESP32.
- Ponte para MCP (milhares de servidores prontos) como "ecossistema"; skills de
  terceiros começam desligadas até eu ligar. Skills são código meu e revisado,
  não uma loja aberta.
- Onde a Alexa ganha: microfones de longe (6 mics), latência (~1 s contra 2–5 s
  do JARVIS), voz neural e catálogo enorme. Onde o JARVIS ganha: entende frases
  livres e encadeia pedidos, permissões por voz de cada pessoa, controla o PC,
  privacidade.
- Dúvidas minhas: que música usar (Spotify só dá controle por API com Premium;
  alternativa gratuita é YouTube Music via yt-dlp) e se ligo uma agenda.

O QUE FALTA (etapa 4, combinado antes)
1. Login no painel (hoje qualquer um no Wi-Fi abre).
2. Acesso de fora de casa pelo celular via Tailscale (com microfone do celular).
3. Subir sozinho com o Windows e reconectar se cair.
4. Suspensão: preciso rodar "powercfg -h off" como administrador.
5. Entrar no PC sem digitar senha depois de acordar (Windows Hello ou
   "exigir entrada após ausência: Nunca") — decisão minha.
6. Investigar a ESP32 instável. 7. Talvez Stream Deck.

O que eu quero de você agora: [ESCREVA AQUI]
