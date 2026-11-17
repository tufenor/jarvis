# Roteiro do JARVIS — o que vem depois

Feito em 21/10/2026, juntando o brainstorm do GPT-5 (`docs/BRAINSTORM_GPT.md`)
com o que eu sei do código. A ordem é minha; onde discordo do GPT, está dito.

## Onde o JARVIS está

Funciona de verdade: microfone sempre aberto, chamado por "Jarvis", conversa
contínua, interrupção, reconhece quem fala, ignora som do próprio PC, 36
ferramentas em 6 skills, 178 testes. Responde em 1,1 a 2,6 s.

O que falta não é mais capacidade. É **confiabilidade e memória**.

---

## Antes de qualquer skill nova: 3 buracos

Eu e o GPT chegamos nos mesmos, por caminhos diferentes.

### 1. Login no painel — BLOQUEIA o acesso externo
Hoje qualquer dispositivo autorizado na rede pode abrir o painel local e mandar comando: abrir
site, rodar ferramenta, ver os sensores. Isso tem que ser resolvido **antes** do
Tailscale, não depois. Sem isso, "acessar de fora de casa" vira buraco aberto.

### 2. Subir sozinho e se recuperar
Hoje o JARVIS precisa ser aberto na mão, e se a rede, a placa ou a API caírem
ele não tenta de novo sozinho. Para ser usado todo dia, tem que subir com o
Windows e reconectar com espera crescente.

### 3. Conversa do quarto ainda vira pedido
Já melhorou muito (som do PC é ignorado, janela caiu para 12 s), mas fala humana
dentro da janela ainda chega ao cérebro. O remédio pronto é ligar
`conversa.exigir_voz_conhecida` depois de cadastrar as vozes.

---

## Primeiras skills, na ordem que eu faria

### 1. Ditado literal
Transcreve direto no campo onde o cursor está, sem passar pelo cérebro.
"Jarvis, começa a ditar" → tudo que for falado é digitado.
Por que primeiro: o Whisper e a digitação **já existem**; é quase só ligar os dois.
É também a função que mais gente usa num assistente de PC.
Cuidado: mostrar prévia antes de colar, para não digitar no campo errado.

### 2. Notas, tarefas e lembretes
"Anota que preciso pagar a internet amanhã às 10." / "Me lembra de sair em 20 minutos."
Por que: é o **buraco da memória**. Hoje o JARVIS resolve o agora e esquece tudo.
Guardar em SQLite (já vem no Python) e disparar pelo próprio laço do servidor —
discordo do GPT aqui: APScheduler é peso desnecessário, o asyncio já dá conta.
Cuidado: repetir a data em voz antes de salvar.

### 3. Cenas de trabalho
"Abre meu ambiente de estudo" → abre os programas, organiza as janelas.
Por que: usa só o que já existe (abrir programa, organizar janela) e é o tipo de
coisa que a Alexa nunca fez. Alto valor, esforço baixo.

### 4. Ler documentos
"Lê esse PDF e me diz os prazos."
Por que: junta com a skill de arquivos que já existe. `pypdf`, `python-docx`,
`openpyxl` — todos gratuitos. Ler por padrão, nunca escrever por cima do original.

### 5. Busca na biblioteca pessoal
"Onde meus contratos falam de reajuste?" — índice SQLite FTS5 nas pastas escolhidas.
Depende da #4.

### Depois, se fizer sentido
Diagnóstico do PC, notas de reunião (com aviso visível de gravação), triagem de
Downloads, assistente de e-mail (rascunho, nunca enviar sozinho).

---

## Automações (ele age sem ser chamado)

Regra que o GPT propôs e eu adoto: **automação avisa no painel, não fala sozinha**,
a não ser que o dono ligue isso de propósito. E nenhuma suspende o PC, instala
nada ou mexe em arquivo sem confirmação.

| gatilho | ação |
|---|---|
| primeiro movimento entre 6h30 e 9h30 | cartão com agenda e ambiente |
| 15 min antes de um compromisso | aviso no painel |
| temperatura/umidade fora da faixa por alguns minutos | um aviso, e só repete depois de normalizar |
| sem movimento por 25-30 min | marca ausente, segura avisos não urgentes |
| Windows volta da suspensão, ou a rede volta | reconecta placa e cérebro com espera crescente |
| voz conhecida detectada | seleciona o perfil para a próxima interação |

---

## A ideia que eu não tinha pensado

**Atalhos que nascem do uso.** O JARVIS olha só o registro local de ferramentas
já aprovadas (nome da ação e hora, nunca áudio) e percebe sequências repetidas.
Depois de ver a mesma sequência algumas vezes, oferece: *"Você costuma abrir
essas três coisas juntas. Quer salvar como rotina?"*

A sugestão nunca roda sozinha: o dono revisa, salva e confirma cada execução.
Vira automação personalizada sem precisar de uma ferramenta de comando livre.

Essa é a melhor ideia do brainstorm, e é barata: os dados já estão no painel.

---

## Sobre o Habblaud

O usuário pediu para chamar "os agentes do ChatGPT no Habblaud". O Habblaud é
outra coisa: um coordenador de sessões do **Claude Code** (servidor local na
porta 4747), e nem estava rodando. Ele não hospeda agentes do ChatGPT.

O GPT foi consultado pelo caminho que existe nesta máquina: **Codex CLI**
(`codex exec`), com um dossiê do projeto pelo stdin. Está anotado na memória
`gpt-via-codex-exec`.
