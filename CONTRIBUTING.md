# Contribuindo com o JARVIS

Ideias de código, correções e melhorias são bem-vindas. O projeto ainda está em desenvolvimento; uma sugestão clara e pequena ajuda mais do que uma mudança grande sem critério de aceite.

## Como propor uma ideia

1. Abra uma [issue de ideia de código](../../issues/new?template=feature_request.yml).
2. Explique o problema, o resultado esperado e como testar.
3. Inclua a área afetada: núcleo Python, interface web, Android, ESP32, integração ou segurança.
4. Se já houver uma implementação, abra um pull request ligado à issue.

Antes de começar uma alteração maior, aguarde o alinhamento na issue. Isso evita trabalho duplicado e mudanças incompatíveis com o desenho do projeto.

## Regras de segurança

- Nunca envie tokens, senhas, cookies, logs privados, endereços de rede, MACs ou arquivos `.env`.
- Não inclua dados de voz, rosto, dispositivo ou cliente sem autorização e anonimização.
- Ações que controlam computador, dispositivos ou contas precisam de confirmação explícita e testes seguros.
- O subprojeto `open-camera-a53/` mantém suas próprias licenças e avisos.

## Pull requests

- Descreva o problema e a solução em linguagem simples.
- Inclua testes ou uma forma reproduzível de verificar a mudança.
- Separe refatoração de mudança de comportamento.
- Não declare suporte a hardware ou sistema operacional que você não testou.

## Ideias sem código

Se você tem apenas uma proposta de produto, use a mesma issue e marque que é uma sugestão. O mantenedor pode transformá-la em uma tarefa técnica depois.
