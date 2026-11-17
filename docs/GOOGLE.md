# Ligar o JARVIS à sua conta Google

Leva uns 10 minutos, é gratuito e você só faz uma vez. **Eu não posso fazer
isso por você**: envolve entrar na sua conta Google e aceitar os termos deles.

O que o JARVIS vai poder fazer depois: **ler sua agenda, marcar compromisso,
procurar e abrir arquivos do Drive**. Ele não apaga evento nem mexe em arquivo
do Drive — isso ficou de fora de propósito.

## 1. Criar o projeto

1. Abra **https://console.cloud.google.com**.
2. No topo, clique no seletor de projetos → **Novo projeto**.
3. Nome: `JARVIS`. Clique em **Criar** e espere terminar.
4. Confirme que o seletor no topo está mostrando **JARVIS**.

## 2. Ligar as duas APIs

1. Menu (☰) → **APIs e serviços** → **Biblioteca**.
2. Procure **Google Calendar API** → clique → **Ativar**.
3. Volte à Biblioteca, procure **Google Drive API** → clique → **Ativar**.

## 3. Dizer que o app é seu

1. Menu → **APIs e serviços** → **Tela de permissão OAuth**.
2. Tipo de usuário: **Externo** → **Criar**.
3. Preencha só o obrigatório: nome do app `JARVIS`, e o seu e-mail nos dois
   campos de contato. **Salvar e continuar** até o fim.
4. Na etapa **Usuários de teste**, clique em **Adicionar usuários** e ponha o
   seu próprio e-mail do Gmail. Sem isso o Google recusa a autorização.

## 4. Baixar as credenciais

1. Menu → **APIs e serviços** → **Credenciais**.
2. **Criar credenciais** → **ID do cliente OAuth**.
3. Tipo de aplicativo: **App para computador**. Nome: `JARVIS`. → **Criar**.
4. Na caixa que aparece, clique em **Baixar JSON**.
5. Renomeie o arquivo baixado para **`google_credenciais.json`** e mova para:

```
dados/google_credenciais.json
```

> Esse arquivo é um segredo seu. Ele está no `.gitignore`, então nunca vai
> para o git. Não cole o conteúdo dele em chat nenhum, nem comigo.

## 5. Autorizar

Com o JARVIS aberto, diga:

> **"Jarvis, autoriza o Google"**

O navegador abre na tela de login do Google. Entre com a sua conta e aceite.
Vai aparecer um aviso de **"app não verificado"** — é esperado, porque o app é
seu e privado. Clique em **Avançado** → **Acessar JARVIS (não seguro)**.

Pronto. O token fica em `dados/google_token.json` (também fora do
git) e se renova sozinho.

## O que dizer depois

- "Jarvis, o que tenho na agenda hoje?"
- "Jarvis, o que tenho essa semana?" (ele olha vários dias)
- "Jarvis, marca dentista amanhã às 15h" → ele **pede confirmação** antes
- "Jarvis, procura o contrato no meu Drive"
- "Jarvis, abre a planilha de gastos do Drive"

## Se algo der errado

| Mensagem | O que fazer |
|---|---|
| "ainda não estou autorizado" | Diga "Jarvis, autoriza o Google" |
| "falta o arquivo de credenciais" | Refaça o passo 4; confira o nome exato do arquivo |
| "o Google respondeu 403" | Falta ativar a API (passo 2) ou você não se pôs como usuário de teste (passo 3.4) |
| Autorização expira em 7 dias | Normal enquanto o app está em modo de teste. Para parar de expirar, publique o app na Tela de permissão OAuth |
