# Dependência MQTT da ponte Alexa

`simple.py` é uma cópia sem alterações de `umqtt.simple`, do projeto oficial
[`micropython-lib`](https://github.com/micropython/micropython-lib), revisão
`90028be0829c6e988b5e239b28f39fb91b6b20e2`.

- Licença: MIT, reproduzida em `LICENSE`.
- SHA-256 de `simple.py` nesta revisão:
  `5458B97FC074DB01263E82AE898727AEE2A15079EA5CFF9D2F6D6ABBEA8EA217`.

Ela aceita um `ssl.SSLContext`, usado pela ESP32 para validar o certificado do
broker MQTT. Não altera os sensores nem as rotas HTTP existentes.
