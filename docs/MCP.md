# Ligar o Claude Desktop ao JARVIS

Depois de ligado, qualquer coisa que você pedir ao Claude Desktop pode virar
pedido ao JARVIS: ler a agenda, buscar arquivo, abrir programa, ligar e
desligar skill, ver os sensores do quarto, falar.

**Essa ponte não é um segundo JARVIS.** Ela conversa com o JARVIS que já está
aberto, por HTTP local. Se o JARVIS não estiver aberto, o conector responde
que ele está offline — nada é feito.

## Por que o Claude Desktop NÃO suspende seu PC

Ações que mudam o estado da máquina (suspender, apagar, instalar programa,
rodar comando livre) **são recusadas** pelo conector. A confirmação do JARVIS
é FALADA, e o Claude Desktop não pode dar esse "sim" por você. Para suspender
o PC, fale com o JARVIS.

## Instalar

1. **Com o JARVIS aberto.** Abra a janela do JARVIS como sempre.

2. **Com uma senha definida.** Se ainda não definiu:

   ```bash
   .venv\Scripts\python.exe -m jarvis --senha
   ```

3. **Edite o arquivo do Claude Desktop:**

   ```
   %APPDATA%\Claude\claude_desktop_config.json
   ```

   Se o arquivo não existir, crie. Cole dentro:

   ```json
   {
     "mcpServers": {
       "jarvis": {
         "command": "C:\\JARVIS\\.venv\\Scripts\\python.exe",
         "args": ["-m", "jarvis.mcp_servidor"]
       }
     }
   }
   ```

4. **Feche e abra o Claude Desktop.** Ele descobre o conector sozinho na
   partida. Na barra de ferramentas vai aparecer o selo com o nome "jarvis".

## Como usar

No Claude Desktop, basta pedir em português. Exemplos:

- *"Jarvis, lista as skills que estão ligadas."*
- *"Peça ao JARVIS a temperatura do quarto."*
- *"Abra o YouTube pelo JARVIS."*
- *"Diga ao JARVIS: toca lofi para estudar."*

## As quatro ferramentas da ponte

| nome | o que faz |
|---|---|
| `listar_ferramentas` | A lista de tudo que o JARVIS pode fazer AGORA (muda com as skills). Chame primeiro quando não souber. |
| `executar` | Roda UMA ferramenta direto, sem passar pelo cérebro. Mais rápido e mais barato. |
| `falar` | Manda um pedido em português, como se tivesse sido falado. O cérebro escolhe a ferramenta. |
| `estado` | Sensores do quarto, uso do PC, alertas, skills ligadas, vozes cadastradas. |

## Se não funcionar

- **"não consegui falar com o JARVIS":** o JARVIS não está aberto. Abra a janela.
- **"HTTP 401":** o conector não entrou. Confere que a senha está definida.
- O Claude Desktop registra o `stderr` do conector; procure por "jarvis" nos
  logs dele.
