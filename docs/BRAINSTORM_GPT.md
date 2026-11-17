# Brainstorm do GPT-5 (Codex CLI) — 21/10/2026

Resposta crua do GPT a um dossiê com o estado real do JARVIS. Minha leitura e a
ordem recomendada estão em docs/ROTEIRO.md.

---

## 1. Doze skills novas, por valor/esforço

1. **Ditado literal — V5/E1 = 5,0**  
   Transcreve diretamente no campo ativo, sem mandar o texto ao cérebro para reformular. **Biblioteca:** faster-whisper e as ferramentas de digitação que já existem.  
   **Exemplos:** “Jarvis, iniciar ditado literal.” / “Pare o ditado e mostre o texto antes de colar.”  
   **Risco principal:** transcrever no campo errado; mostrar prévia antes de inserir.

2. **Notas, tarefas e lembretes — V5/E2 = 2,5**  
   Guarda uma nota ou tarefa e dispara lembretes mesmo depois de reiniciar o JARVIS. **Biblioteca:** `sqlite3` (incluída no Python), APScheduler e dateparser para datas em português. [APScheduler](https://apscheduler.readthedocs.io/en/master/userguide.html), [dateparser](https://dateparser.readthedocs.io/en/stable/index.html)  
   **Exemplos:** “Anota que preciso pagar a internet amanhã às 10.” / “Me lembra de sair daqui a 20 minutos.”  
   **Risco principal:** entender errado a data; repetir horário e conteúdo em voz antes de salvar.

3. **Diagnóstico do PC e do JARVIS — V4/E2 = 2,0**  
   Resume uso de CPU, memória, disco e rede e verifica microfone, cérebro e ESP32. **Biblioteca:** `psutil` para o PC; HTTP já usado pelo projeto para consultar a placa. [psutil](https://psutil.readthedocs.io/stable/index.html)  
   **Exemplos:** “O que está deixando o PC lento agora?” / “Confira se a placa, o microfone e o cérebro estão online.”  
   **Risco principal:** confundir sintomas com causa; manter o diagnóstico em leitura e apresentar evidências, sem encerrar processos.

4. **Notas de reunião — V4/E2 = 2,0**  
   Inicia e encerra uma gravação sob comando; gera transcrição, resumo e lista de decisões. **Bibliotecas:** `soundcard`, faster-whisper e sherpa-onnx, que já fazem parte do fluxo de áudio descrito.  
   **Exemplos:** “Comece a anotar esta reunião.” / “Encerre e liste decisões e responsáveis.”  
   **Risco principal:** gravar pessoas sem que saibam; gravação explícita, indicador visível e retenção local configurável.

5. **Cenas de trabalho — V5/E3 = 1,67**  
   Prepara combinações nomeadas de programas e janelas, como “estudo”, “gravação” ou “reunião”. **Biblioteca:** as ferramentas atuais de programas e janelas; `pywinauto` pode ajudar com controles do Windows que ainda não estejam acessíveis. [pywinauto](https://github.com/pywinauto/pywinauto)  
   **Exemplos:** “Abra meu ambiente de estudo.” / “Prepare a tela para gravar: navegador e pasta do projeto.”  
   **Risco principal:** abrir ou mover janelas inesperadamente; mostrar a sequência e pedir confirmação antes de aplicar.

6. **Leitor de documentos locais — V4/E3 = 1,33**  
   Lê PDFs, Word e planilhas; responde com referência à página, planilha ou célula. Pode gerar uma cópia nova para revisão. **Bibliotecas:** `pypdf`, `python-docx` e `openpyxl`. PDF escaneado pode exigir OCR, pois `pypdf` extrai texto, mas não reconhece texto em imagens. [pypdf](https://pypdf.readthedocs.io/en/latest/user/extract-text.html), [python-docx](https://python-docx.readthedocs.io/en/latest/user/quickstart.html), [openpyxl](https://openpyxl.readthedocs.io/en/stable/development.html)  
   **Exemplos:** “Leia este PDF e me diga os prazos.” / “Faça uma cópia deste relatório com um resumo no início.”  
   **Risco principal:** extração incorreta ou escrita sobre o original; leitura por padrão e gravação em cópia.

7. **Busca na biblioteca pessoal — V5/E4 = 1,25**  
   Indexa pastas escolhidas e encontra trechos em vários documentos, com nome do arquivo e localização. **Biblioteca:** SQLite FTS5, integrado ao SQLite, mais os parsers do leitor de documentos. [SQLite FTS5](https://www.sqlite.org/fts5.html)  
   **Exemplos:** “Onde meus contratos falam de reajuste?” / “Mostre os trechos sobre a garantia deste aparelho.”  
   **Risco principal:** indexar documentos privados; limitar a pastas escolhidas e manter a busca local.

8. **Triagem de Downloads — V3/E3 = 1,0**  
   Detecta arquivos novos e sugere agrupamentos, como notas fiscais, PDFs ou instaladores. **Biblioteca:** `watchdog` para observar alterações na pasta e `pathlib`, já incluída no Python. [watchdog](https://github.com/gorakhargosh/watchdog)  
   **Exemplos:** “Quais arquivos novos parecem ser notas fiscais?” / “Sugira onde organizar os arquivos desta semana.”  
   **Risco principal:** classificar ou mover algo errado; começar apenas sugerindo e pedir confirmação para mover.

9. **Assistente de e-mail — V4/E4 = 1,0**  
   Resume mensagens e prepara rascunhos; não envia por conta própria. **Biblioteca:** `google-api-python-client`, com OAuth do usuário e escopo mínimo. Isso depende da API remota do Gmail e da configuração da conta. [Guia oficial da Gmail API](https://developers.google.com/workspace/gmail/api/quickstart/python)  
   **Exemplos:** “Resuma minhas mensagens não lidas desta manhã.” / “Prepare um rascunho aceitando a reunião do João.”  
   **Risco principal:** privacidade da caixa postal e escopos OAuth; envio sempre confirmado pelo usuário.

10. **Rotinas compostas — V4/E4 = 1,0**  
    Executa uma sequência fixa de ferramentas já permitidas, como consultar a agenda e abrir programas específicos. **Biblioteca:** `jsonschema` para validar rotinas estruturadas; ferramentas atuais para as ações.  
    **Exemplos:** “Crie uma rotina para preparar minha reunião.” / “Execute minha rotina de começo do dia.”  
    **Risco principal:** um passo errado amplia o efeito dos seguintes; mostrar a sequência e pedir confirmação antes de iniciar.

11. **Casa conectada local — V4/E5 = 0,8**  
    Integra com Home Assistant para consultar sensores e controlar dispositivos cadastrados. Só compensa se o usuário já tiver ou decidir instalar essa plataforma. **Biblioteca:** `httpx` para a API local; a API exige token de acesso. [API REST do Home Assistant](https://github.com/home-assistant/developers.home-assistant/blob/master/docs/api/rest.md)  
    **Exemplos:** “Como está a sala?” / “Ligue a cena de descanso da sala.”  
    **Risco principal:** comandar o dispositivo errado; permitir apenas entidades cadastradas e confirmar mudanças de estado.

12. **Leitor da aba do navegador — V4/E5 = 0,8**  
    Resume uma página aberta e pode preparar um formulário para revisão. **Biblioteca:** Playwright, gratuito e de código aberto; funciona como ferramenta local de automação do navegador. [Documentação do Playwright para Python](https://playwright.dev/python/docs/intro)  
    **Exemplos:** “Leia esta aba e me diga os três pontos principais.” / “Preencha o formulário e me mostre antes de enviar.”  
    **Risco principal:** conteúdo da página pode tentar induzir ações ou expor dados; começar em modo de leitura, sem envio ou compra.

## 2. Seis automações sem chamada

Para respeitar o funcionamento atual, elas podem atualizar o painel e gerar avisos locais sem wake word. **Fala proativa seria uma opção separada.** Nenhuma suspenderia o PC, instalaria programas ou alteraria arquivos sem a confirmação falada já exigida.

1. **Resumo da manhã**  
   **Gatilho:** primeiro movimento entre 6h30 e 9h30, uma vez ao dia, com o PC ativo.  
   **Ação:** montar um cartão com agenda e leituras ambientais; só incluir conteúdo pessoal se o perfil autorizado estiver identificado.

2. **Lembrete de compromisso**  
   **Gatilho:** 15 minutos antes de um evento, com o PC ativo.  
   **Ação:** mostrar o aviso no painel; evitar falar detalhes pessoais se não houver perfil autorizado.

3. **Alerta de ambiente**  
   **Gatilho:** temperatura ou umidade acima do limite escolhido por alguns minutos, com movimento recente.  
   **Ação:** mostrar um aviso único no painel e aguardar a leitura voltar à faixa normal antes de alertar de novo; não controlar aparelhos.

4. **Modo “sala vazia”**  
   **Gatilho:** sem movimento por 25–30 minutos e PC sem atividade recente.  
   **Ação:** marcar o JARVIS como ausente e guardar avisos não urgentes para depois; não suspender nem silenciar o Windows.

5. **Recuperação após retorno do PC ou da rede**  
   **Gatilho:** Windows inicia ou retorna da suspensão, ou a rede volta.  
   **Ação:** tentar reconectar ESP32 e cérebro com intervalos crescentes, atualizar o estado do painel e manter as ferramentas locais disponíveis se a rede falhar.

6. **Contexto de locutor**  
   **Gatilho:** o reconhecimento local detecta uma voz cadastrada enquanto há presença no ambiente.  
   **Ação:** selecionar internamente o perfil para a próxima interação, sem falar agenda nem executar ferramentas. A impressão de voz serve para personalização; não deve liberar ações sensíveis.

## 3. Cinco maiores lacunas para uso diário

1. **Acesso ao painel:** o contexto do projeto registra que o painel ainda pode ser acessado pela rede local sem login. Autenticação e limites de permissão vêm antes de qualquer acesso externo; Tailscale é uma etapa posterior.

2. **Recuperação automática:** ainda falta fechar o ciclo de inicialização e reconexão do próprio JARVIS, da ESP32 e do cérebro. O histórico também registra instabilidade de conexão com a placa.

3. **Falsos pedidos e privacidade:** conversas do ambiente podem entrar na janela de conversa e virar pedidos, chamadas e respostas fora de contexto. Isso cria interrupção e uso desnecessário da API.

4. **Memória prática entre sessões:** faltam notas, tarefas e lembretes duráveis. Sem isso, o JARVIS controla muitas coisas no momento, mas não ajuda a lembrar o que ficou para depois.

5. **Integrações verificadas no uso real:** Agenda e Drive dependem de OAuth do usuário e ainda não foram validados com a conta real, segundo o status consultado. Também vale validar voz humana, múltiplos locutores e falhas de rede em condições cotidianas.

## 4. Uma ideia menos óbvia: atalhos que surgem do uso

O JARVIS poderia observar **somente o registro local de ferramentas aprovadas** — nomes das ações e horários, sem guardar áudio — e detectar sequências repetidas. Depois de observar a mesma sequência algumas vezes, oferece: “Você costuma abrir estes três itens juntos. Quer salvar como rotina?”

A sugestão nunca executa sozinha: o usuário revisa, salva e confirma cada execução. Isso transforma o uso real em atalhos pessoais sem criar uma ferramenta de comando irrestrito.

