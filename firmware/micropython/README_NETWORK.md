# Firmware JARVIS: sensores, LCD, Wi-Fi e Bluetooth

O acompanhamento e os resultados dos testes ficam somente em
[`PROJECT_CONTEXT.md`](../../PROJECT_CONTEXT.md). Este README descreve instalação e uso.

## Primeira gravação

A primeira gravação deve ser feita pelo USB-C de dados. Depois de enviado como `main.py`, o firmware:

1. anuncia Bluetooth como `JARVIS-ESP32`;
2. tenta conectar à rede salva;
3. se não houver rede salva, cria o Wi-Fi `JARVIS-SETUP`;
4. expõe `http://192.168.4.1` para cadastrar SSID, senha, token local e IP do PC;
5. grava esses valores localmente em `wifi.json` e reinicia.

Senha do Wi-Fi de configuração: definida por você no primeiro boot (`DEFINA_A_SENHA_DE_SETUP` no código). Não use senha padrão.
O token deve ser aleatório, ter exatamente 32 caracteres hexadecimais e ser
mantido privado. Tanto ele quanto a senha Wi-Fi ficam em texto simples na flash
local da placa; não os envie pelo chat.

## Envio inicial

Confirme a porta serial disponível e preserve uma cópia do `main.py` atual antes
de substituir arquivos. Envie o driver antes do programa principal; não apague
`wifi.json` nem o firmware MicroPython. Pare se algum comando falhar.

```powershell
C:\JARVIS\.venv\Scripts\python.exe -m mpremote connect COM7 fs cp C:\JARVIS\firmware\micropython\wake_on_lan.py :wake_on_lan.py
C:\JARVIS\.venv\Scripts\python.exe -m mpremote connect COM7 fs cp C:\JARVIS\firmware\micropython\lcd_display.py :lcd_display.py
C:\JARVIS\.venv\Scripts\python.exe -m mpremote connect COM7 fs cp C:\JARVIS\firmware\micropython\mobile_panel.py :mobile_panel.py
C:\JARVIS\.venv\Scripts\python.exe -m mpremote connect COM7 fs cp C:\JARVIS\firmware\micropython\main_network.py :main.py
C:\JARVIS\.venv\Scripts\python.exe -m mpremote connect COM7 reset
```

Depois, conecte o celular ou PC ao Wi-Fi `JARVIS-SETUP`, abra `http://192.168.4.1`,
informe a rede local e um token aleatório de 32 dígitos hexadecimais. O valor
fica na placa e será pedido no painel ao despertar o PC (não é guardado pelo
navegador).
Na rede local, `POST http://<ip-da-esp32>/wake` envia um magic packet UDP para
o MAC Wi-Fi do PC configurado localmente, usando o broadcast calculado da sub-rede.
Uma resposta HTTP 200 confirma somente o envio do pacote, não que o PC acordou.
Este firmware não abre portas no roteador nem envia o token para fora da LAN.
O HTTP local não usa TLS; use somente na rede doméstica confiável e não exponha
essa porta à internet.

## Painel do iPhone e do computador

Depois de a ESP32 conectar ao Wi-Fi, consulte o IP mostrado no log serial
(`WIFI: conectado <IP>`) e abra `http://<IP>` no Safari do iPhone ou em qualquer
navegador do computador conectado à mesma rede. A tela mostra temperatura,
umidade, movimento e LED, atualiza a cada 3 segundos, controla o LED e envia
`POST /wake` com o token digitado. No iPhone, use Compartilhar → Adicionar à
Tela de Início para criar um atalho visual. É uma página web local, não um app
nativo; áudio/microfone remoto não faz parte deste painel.

Se o Wi-Fi da ESP32 ainda não foi configurado, entre na rede `JARVIS-SETUP` e
abra `http://192.168.4.1` para preencher o formulário. O token e a senha Wi-Fi
ficam em texto simples na flash da placa. O token também trafega sem TLS na
rede local; mantenha tudo somente na rede doméstica e não publique a porta.
O painel pode enviar o pacote de despertar mesmo com o PC desligado, mas a
ESP32 precisa continuar ligada e o PC precisa aceitar Wake-on-WLAN. Isso ainda
requer teste real de suspensão; o HTTP 200 sozinho não prova que o computador
acordou.

## Desligamento do PC (agente Windows local)

Despertar e desligar são mecanismos diferentes. A ESP32 envia Wake-on-WLAN sem
precisar do PC ligado. Para desligar, o PC precisa estar ligado e o agente local
precisa estar executando.

1. No PC, execute `scripts\\configurar_pc_agent.bat`. Digite duas vezes o mesmo
   token local de 32 caracteres que será cadastrado no portal da ESP32. O campo
   não aparece enquanto é digitado; no PC é guardado apenas o hash SHA-256.
   A rede padrão é `192.168.50.0/24`, como exemplo. Use a
   rede exata se ela mudar.
2. Execute `scripts\\iniciar_pc_agent.bat` e deixe a janela ativa enquanto quiser
   usar os controles de energia. Se o Firewall do Windows perguntar, permita
   somente rede privada/local. Não crie encaminhamento de porta no roteador.
3. No portal local `JARVIS-SETUP`, informe a senha Wi-Fi diretamente no iPhone,
   gere/anote o token local e informe o IP privado do PC (por exemplo, `192.168.50.10`).
   A senha e o token ficam sem criptografia na flash ESP32; o PC guarda apenas
   o hash do token. Não compartilhe senha/token no chat.
4. Depois do reinício, abra o IP da ESP32 no Safari pela rede de casa, digite o
   token no painel e adicione a página à Tela de Início.

O botão de desligar pede confirmação e agenda `shutdown.exe /s /t 30` sem
forçar o fechamento de aplicativos; salve o trabalho antes. O painel oferece
cancelamento do desligamento agendado. As rotas só aceitam o token configurado
e o agente só aceita clientes dentro da sub-rede privada cadastrada; os únicos
comandos possíveis são desligar e cancelar, sem shell ou comandos arbitrários.
O serviço escuta na LAN enquanto estiver rodando. Não o exponha à internet.
O IP do PC deve ficar estável (idealmente com reserva DHCP no roteador).

O agente não inicia automaticamente com o Windows por padrão: isso evita deixar
uma API de energia ligada sem a decisão explícita do usuário. Inicie-o antes de
usar o painel para desligar o PC. O botão de despertar não depende do agente.

O Bluetooth nesta primeira versão é um anúncio de presença. O canal de comandos BLE será adicionado depois da API Wi-Fi autenticada.

## LCD e sensores

Sem alterar a montagem atual: LED GPIO4, DHT11 DATA GPIO6, PIR OUT GPIO7,
LCD SDA GPIO15 e SCL GPIO16, I2C(0) a 10 kHz, endereço 0x27.
LCD VCC continua em 3V3 e GND comum; não mudar para 5 V diretamente nos GPIOs.

O programa recria automaticamente a tela ao reiniciar:

```text
T:31C U:08%
Movimento: SIM
```

Os números acima são um exemplo, não valores fixos ou calibrados. O DHT11 é lido
a cada 2,5 s. Falha de leitura (ou retorno 0 °C/0% suspeito) limpa os valores e
mostra `Sem leitura`. O PIR mostra `SIM` ou `NAO`. A tela é atualizada no máximo
uma vez por segundo, escrevendo apenas linhas que mudaram para reduzir cintilação.

Se o LCD não responder, o programa registra a falha e tenta reconectar depois
de cinco segundos, sem encerrar o loop de LED, sensores e servidor. Esses
intervalos não são garantias de tempo real: chamadas I2C/HTTP têm latência.

## Testes no computador

```powershell
cd C:\JARVIS
C:\JARVIS\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

A suíte executa o driver e o firmware com hardware/rede simulados, cobrindo
formatação, atualização, falhas e recuperação. Ela não substitui a verificação
na ESP32 e a confirmação visual na tela.

## Restauração da versão anterior ao LCD

Use somente se precisar desfazer esta integração. A cópia preservada e verificada
fica em `firmware/backups/lcd-20261018/main_network_before_lcd.py`; existe também
`main_before_lcd_20261018.py` na placa. Não sobrescreva esses backups.

```powershell
C:\JARVIS\.venv\Scripts\python.exe -m mpremote connect COM7 fs cp C:\JARVIS\firmware\backups\lcd-20261018\main_network_before_lcd.py :main.py
C:\JARVIS\.venv\Scripts\python.exe -m mpremote connect COM7 reset
```

Não é necessário apagar `lcd_display.py` para voltar ao programa anterior.
