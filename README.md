# JARVIS — assistente pessoal local

Assistente pessoal para Windows com processamento local, voz em português e automação controlada do computador. O PC é o cérebro; placas ESP32 e um aplicativo Android funcionam como sensores, atuadores e controle remoto.

Projeto em desenvolvimento. Este repositório é o código-fonte modular — não um produto pronto.

## Como está organizado

| Pasta | Papel |
|---|---|
| `jarvis/` | núcleo do assistente: interface, rotas e orquestração |
| `skills/` | habilidades plugáveis (comando, memória, arquivos, celular, automação visual…) |
| `firmware/micropython/` | firmware da ESP32-S3: sensores, LCD, relé e wake-on-LAN |
| `mobile-android/` | app companion em Kotlin/Compose |
| `integracoes/alexa/` | ponte de integração |
| `native/credential_provider/` | provedor local de credencial |
| `seguranca/` | regras de permissão e limites de ação |
| `tests/` | testes do núcleo e do agente do PC |
| `docs/` | decisões de arquitetura (ADRs) e notas de integração |

## Stack

- **Núcleo:** Python, FastAPI
- **Firmware:** MicroPython em ESP32-S3 (sensores, LCD I2C, relé, wake-on-LAN)
- **Android:** Kotlin, Jetpack Compose
- **Integrações:** voz em português, ferramentas locais do Windows, HTTP

## Princípios do projeto

1. **Ação com limite.** Automação que afeta o computador pede confirmação e tem escopo definido; nada de "faça tudo" sem controle.
2. **Local primeiro.** O processamento e a memória ficam na máquina; integrações externas são opcionais.
3. **Falha explicada.** Todo erro precisa de log que diga o que aconteceu, não só que falhou.
4. **Modular.** Cada habilidade pode ser desligada sem derrubar o resto.

## Como sugerir código

Encontrou uma melhoria, integração ou teste que faria sentido aqui? Abra uma [issue de ideia](../../issues/new?template=feature_request.yml). Para um defeito, use o [modelo de bug](../../issues/new?template=bug_report.yml). A [guia de contribuição](CONTRIBUTING.md) explica o que testar e quais dados nunca devem ser publicados.

## Rodando o núcleo

```bash
cd jarvis
pip install -r requirements.txt
python -m jarvis
```

O firmware é gravado separadamente na placa (veja `firmware/micropython/README_NETWORK.md`).

## Segurança

- Nenhum token, senha, chave ou `.env` real neste repositório. Token do relay e senha do ponto de acesso de configuração são placeholders (`DEFINA_SEU_TOKEN`, `DEFINA_A_SENHA_DE_SETUP`) e devem ser trocados no primeiro boot.
- Configurações de máquina e credenciais ficam fora do Git, em arquivos locais ignorados.
- O projeto foi desenhado para não operar em dados de terceiros sem pedido explícito.

## Estado

Em desenvolvimento ativo. O histórico de hardware e os testes de bancada estão documentados localmente; aqui ficam o código e as decisões de arquitetura.

## Autor

Projeto publicado pela conta `tufenor`. Não inclua dados pessoais, credenciais
ou identificadores de dispositivos ao abrir issues ou pull requests.
