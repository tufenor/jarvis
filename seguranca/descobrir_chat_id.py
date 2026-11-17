"""Descobre o seu chat_id do Telegram. Mande qualquer mensagem pro bot antes."""
import json, os, sys
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
    cfg = json.load(f)

token = cfg.get("telegram_token", "")
if "COLOQUE" in token or not token:
    print("Primeiro preencha 'telegram_token' no config.json (veja LEIA-ME.txt).")
    sys.exit(1)

print("Procurando mensagens enviadas ao bot...\n")
resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
dados = resp.json()

if not dados.get("ok"):
    print("O Telegram recusou o token. Confira se copiou certo.")
    print(str(dados)[:300])
    sys.exit(1)

encontrados = {}
for item in dados.get("result", []):
    msg = item.get("message") or item.get("edited_message") or {}
    chat = msg.get("chat") or {}
    if chat.get("id"):
        nome = chat.get("first_name") or chat.get("title") or "sem nome"
        encontrados[chat["id"]] = nome

if not encontrados:
    print("Nenhuma mensagem encontrada.")
    print("Abra o Telegram, procure o seu bot e mande um 'oi' pra ele.")
    print("Depois rode este arquivo de novo.")
    sys.exit(0)

print("Chat IDs encontrados:\n")
for chat_id, nome in encontrados.items():
    print(f"   {chat_id}   ({nome})")
print("\nCopie o numero e cole em 'telegram_chat_id' no config.json")
