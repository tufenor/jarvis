# Programação local do JARVIS

A skill `programacao` foi adicionada ao conjunto local de ferramentas. Ela
trabalha somente em `projetos` (configurável em `config.json`) e não
é um terminal genérico.

## Fluxo

1. O JARVIS lista ou lê o projeto sem alterar arquivos.
2. Ao criar ou editar, ele mostra o arquivo e pede confirmação para aquela
   gravação.
3. Depois de gravar, testar é uma segunda ação e pede nova confirmação.
4. Os testes permitidos são apenas sintaxe de Python/JavaScript ou `unittest`
   da pasta `tests`; não existe argumento de shell livre nessa skill.

Credenciais, arquivos `.env`, configurações privadas e tokens ficam fora do
escopo da skill. A Alexa pode encaminhar o pedido de programação pelo canal
MQTT já preparado, mas o JARVIS local continua sendo quem pede confirmações e
executa as etapas.
