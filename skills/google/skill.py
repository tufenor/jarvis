"""Google Agenda e Google Drive.

O que o JARVIS pode: LER a agenda e CRIAR evento; PROCURAR e ABRIR no Drive.
Apagar evento e mexer em arquivo do Drive ficaram de fora de propósito —
são coisas que um erro de transcrição não deveria conseguir fazer.

Credenciais: o usuário baixa `dados/google_credenciais.json` do Google Cloud
(ver `docs/GOOGLE.md`). O token fica em `dados/google_token.json`. Os dois
estão fora do git. Nada de chave escrita no código.
"""
import asyncio
import re
from datetime import datetime, time, timedelta
from pathlib import Path

from jarvis.ferramentas import ErroFerramenta, Ferramenta

RAIZ = Path(__file__).resolve().parents[2]
CREDENCIAIS = RAIZ / "dados" / "google_credenciais.json"
TOKEN = RAIZ / "dados" / "google_token.json"

# Só o necessário: criar evento na agenda, LER o Drive, LER e ENVIAR Gmail,
# e LER histórico/playlists do YouTube. O escopo drive.file foi omitido:
# o Google rejeita a combinação drive.file + youtube.readonly no mesmo pedido.
# O Drive permanece somente leitura, como definido para esta integração.
ESCOPOS = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/youtube.readonly",
]
MEMORIA_NOME = "jarvis_memoria.json"

DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _credenciais(interativo=False):
    """Devolve credenciais válidas, renovando o token quando dá."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    cred = None
    if TOKEN.is_file():
        try:
            cred = Credentials.from_authorized_user_file(str(TOKEN), ESCOPOS)
        except ValueError:
            cred = None
    if cred and cred.valid:
        return cred
    if cred and cred.expired and cred.refresh_token:
        cred.refresh(Request())
        TOKEN.write_text(cred.to_json(), encoding="utf-8")
        return cred
    if not interativo:
        raise ErroFerramenta(
            "ainda não estou autorizado na sua conta Google. Diga: Jarvis, autoriza o Google"
        )
    if not CREDENCIAIS.is_file():
        raise ErroFerramenta(
            "falta o arquivo de credenciais do Google. Veja as instruções em docs barra GOOGLE ponto M D"
        )
    fluxo = InstalledAppFlow.from_client_secrets_file(str(CREDENCIAIS), ESCOPOS)
    cred = fluxo.run_local_server(port=0, prompt="consent")
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(cred.to_json(), encoding="utf-8")
    return cred


def _servico(nome, versao, interativo=False):
    from googleapiclient.discovery import build
    return build(nome, versao, credentials=_credenciais(interativo), cache_discovery=False)


def _erro_legivel(exc):
    from googleapiclient.errors import HttpError
    if isinstance(exc, HttpError):
        return f"o Google respondeu {exc.resp.status}"
    if isinstance(exc, ErroFerramenta):
        return str(exc)
    return f"{type(exc).__name__}"


def quando_em_palavras(inicio, agora=None):
    """'2026-10-22T14:00:00-03:00' -> 'amanhã às 14h'."""
    agora = agora or datetime.now()
    if len(inicio) == 10:  # dia inteiro
        dia = datetime.strptime(inicio, "%Y-%m-%d").date()
        hora = ""
    else:
        quando = datetime.fromisoformat(inicio)
        # Sem zero à esquerda: falado, "09h30" sairia estranho.
        hora = f" às {quando.hour}h{quando.minute:02d}".replace("h00", "h")
        dia = quando.date()
    diferenca = (dia - agora.date()).days
    if diferenca == 0:
        nome = "hoje"
    elif diferenca == 1:
        nome = "amanhã"
    elif 0 < diferenca < 7:
        nome = DIAS[dia.weekday()]
    else:
        nome = f"{dia.day} de {MESES[dia.month - 1]}"
    return nome + hora


def interpretar_quando(texto, agora=None):
    """Aceita 'amanhã às 15h', 'hoje 9:30' ou uma data ISO. Devolve datetime."""
    agora = agora or datetime.now()
    limpo = texto.strip().lower()
    try:
        return datetime.fromisoformat(texto.strip())
    except ValueError:
        pass
    dia = agora.date()
    if "amanh" in limpo:
        dia += timedelta(days=1)
    elif "depois de amanh" in limpo:
        dia += timedelta(days=2)
    else:
        for i, nome in enumerate(DIAS):
            if nome in limpo:
                adiante = (i - agora.weekday()) % 7 or 7
                dia = agora.date() + timedelta(days=adiante)
                break
    m = re.search(r"(\d{1,2})\s*(?::|h|horas?)\s*(\d{2})?", limpo)
    if not m:
        raise ErroFerramenta("não entendi o horário; diga algo como 'amanhã às 15h'")
    hora, minuto = int(m.group(1)), int(m.group(2) or 0)
    if not (0 <= hora <= 23 and 0 <= minuto <= 59):
        raise ErroFerramenta("esse horário não existe")
    return datetime.combine(dia, time(hora, minuto))


def criar(contexto):
    abrir = contexto["abrir"]
    memoria = contexto.get("memoria")

    def _sync_automatico():
        """Faz upload silencioso no Drive quando a memória muda."""
        if not TOKEN.is_file():
            return  # ainda não autorizado: o próximo autorizar_google liga tudo.
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return
        if loop.is_running():
            loop.create_task(_tentar_salvar_memoria())

    async def _tentar_salvar_memoria():
        try:
            await salvar_memoria_no_drive()
        except ErroFerramenta:
            pass  # sem autorização ou offline: silencioso de propósito.

    async def autorizar_google():
        if not CREDENCIAIS.is_file():
            raise ErroFerramenta(
                "primeiro você precisa baixar o arquivo de credenciais do Google Cloud; "
                "as instruções estão no arquivo docs barra GOOGLE"
            )
        # Abre o navegador para o usuário aprovar; a janela é dele, não minha.
        await asyncio.to_thread(_credenciais, True)
        return "Pronto, estou autorizado na sua conta Google."

    async def ver_agenda(dias=1):
        if not 1 <= dias <= 30:
            raise ErroFerramenta("posso ver de 1 a 30 dias")

        def buscar():
            servico = _servico("calendar", "v3")
            agora = datetime.now().astimezone()
            fim = agora + timedelta(days=dias)
            r = servico.events().list(
                calendarId="primary", timeMin=agora.isoformat(), timeMax=fim.isoformat(),
                singleEvents=True, orderBy="startTime", maxResults=15,
            ).execute()
            return r.get("items", [])
        try:
            eventos = await asyncio.to_thread(buscar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui ler a agenda: {_erro_legivel(exc)}")
        if not eventos:
            return "Nada na agenda" + (" para hoje." if dias == 1 else f" para os próximos {dias} dias.")
        partes = []
        for e in eventos[:8]:
            inicio = e["start"].get("dateTime") or e["start"].get("date")
            partes.append(f"{quando_em_palavras(inicio)}: {e.get('summary', 'sem título')}")
        return "Na agenda: " + "; ".join(partes) + "."

    async def criar_evento(titulo, quando, duracao_min=60):
        if not 5 <= duracao_min <= 1440:
            raise ErroFerramenta("a duração tem que ficar entre 5 minutos e 24 horas")
        inicio = interpretar_quando(quando)

        def gravar():
            servico = _servico("calendar", "v3")
            corpo = {
                "summary": titulo,
                "start": {"dateTime": inicio.astimezone().isoformat()},
                "end": {"dateTime": (inicio + timedelta(minutes=duracao_min)).astimezone().isoformat()},
            }
            return servico.events().insert(calendarId="primary", body=corpo).execute()
        try:
            await asyncio.to_thread(gravar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui criar o evento: {_erro_legivel(exc)}")
        return f"Marquei {titulo} para {quando_em_palavras(inicio.isoformat())}."

    async def procurar_no_drive(nome):
        def buscar():
            servico = _servico("drive", "v3")
            # O nome vai como parâmetro da consulta, não concatenado cru.
            seguro = nome.replace("\\", "\\\\").replace("'", "\\'")
            r = servico.files().list(
                q=f"name contains '{seguro}' and trashed = false",
                fields="files(id, name, mimeType, webViewLink, modifiedTime)",
                pageSize=10, orderBy="modifiedTime desc",
            ).execute()
            return r.get("files", [])
        try:
            arquivos = await asyncio.to_thread(buscar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui procurar no Drive: {_erro_legivel(exc)}")
        if not arquivos:
            return f"Não achei nada no Drive com '{nome}'."
        nomes = "; ".join(a["name"] for a in arquivos[:6])
        return f"Achei {len(arquivos)} no Drive: {nomes}."

    async def ler_emails(quantidade=5, busca=""):
        if not 1 <= quantidade <= 20:
            raise ErroFerramenta("posso ler de 1 a 20 e-mails por vez")

        def buscar():
            servico = _servico("gmail", "v1")
            consulta = busca or "is:unread"
            r = servico.users().messages().list(
                userId="me", maxResults=quantidade, q=consulta,
            ).execute()
            saida = []
            for m in r.get("messages", []):
                detalhe = servico.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                cab = {h["name"]: h["value"] for h in detalhe["payload"].get("headers", [])}
                saida.append({
                    "de": cab.get("From", "desconhecido"),
                    "assunto": cab.get("Subject", "sem assunto"),
                    "resumo": detalhe.get("snippet", "")[:120],
                })
            return saida
        try:
            emails = await asyncio.to_thread(buscar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui ler o Gmail: {_erro_legivel(exc)}")
        if not emails:
            return "Nenhum e-mail novo." if not busca else f"Nenhum e-mail para '{busca}'."
        partes = [f"{e['de'].split('<')[0].strip()}: {e['assunto']}" for e in emails[:5]]
        return f"Tem {len(emails)} e-mail: " + "; ".join(partes) + "."

    async def enviar_email(destinatario, assunto, corpo):
        import base64
        from email.mime.text import MIMEText
        if "@" not in destinatario or "." not in destinatario.split("@")[-1]:
            raise ErroFerramenta("o destinatário não parece um e-mail válido")
        if len(corpo) > 20000:
            raise ErroFerramenta("corpo grande demais; máximo 20000 caracteres")

        def enviar():
            servico = _servico("gmail", "v1")
            msg = MIMEText(corpo, "plain", "utf-8")
            msg["to"] = destinatario
            msg["subject"] = assunto
            codificado = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            return servico.users().messages().send(
                userId="me", body={"raw": codificado},
            ).execute()
        try:
            await asyncio.to_thread(enviar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui enviar: {_erro_legivel(exc)}")
        return f"Enviado para {destinatario}."

    def _achar_memoria(servico):
        r = servico.files().list(
            q=f"name = '{MEMORIA_NOME}' and trashed = false",
            fields="files(id, name, modifiedTime)", pageSize=1,
        ).execute()
        arquivos = r.get("files", [])
        return arquivos[0] if arquivos else None

    async def salvar_memoria_no_drive():
        if memoria is None:
            raise ErroFerramenta("a memória não está ativa neste JARVIS")
        from googleapiclient.http import MediaInMemoryUpload

        def enviar():
            servico = _servico("drive", "v3")
            dados = memoria.como_json().encode("utf-8")
            midia = MediaInMemoryUpload(dados, mimetype="application/json", resumable=False)
            existente = _achar_memoria(servico)
            if existente:
                return servico.files().update(fileId=existente["id"], media_body=midia).execute()
            return servico.files().create(
                body={"name": MEMORIA_NOME}, media_body=midia, fields="id",
            ).execute()
        try:
            await asyncio.to_thread(enviar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui salvar no Drive: {_erro_legivel(exc)}")
        return f"Salvei a memória no Drive ({len(memoria.itens)} itens)."

    async def restaurar_memoria_do_drive():
        if memoria is None:
            raise ErroFerramenta("a memória não está ativa neste JARVIS")
        import json as _json

        def baixar():
            servico = _servico("drive", "v3")
            existente = _achar_memoria(servico)
            if not existente:
                return None
            return servico.files().get_media(fileId=existente["id"]).execute()
        try:
            conteudo = await asyncio.to_thread(baixar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui baixar do Drive: {_erro_legivel(exc)}")
        if conteudo is None:
            return "Não há backup de memória no Drive ainda."
        try:
            itens = _json.loads(conteudo)
        except (ValueError, TypeError):
            raise ErroFerramenta("o backup no Drive está corrompido")
        memoria.substituir(itens)
        return f"Memória restaurada do Drive ({len(memoria.itens)} itens)."

    async def ver_inscricoes_youtube(quantidade=10):
        if not 1 <= quantidade <= 25:
            raise ErroFerramenta("posso listar de 1 a 25 inscrições")

        def buscar():
            servico = _servico("youtube", "v3")
            r = servico.subscriptions().list(
                part="snippet", mine=True, maxResults=quantidade, order="relevance",
            ).execute()
            return [item["snippet"]["title"] for item in r.get("items", [])]
        try:
            canais = await asyncio.to_thread(buscar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui ler o YouTube: {_erro_legivel(exc)}")
        if not canais:
            return "Você não tem inscrições."
        return f"Inscrições principais: {', '.join(canais[:8])}."

    async def abrir_do_drive(nome):
        def buscar():
            servico = _servico("drive", "v3")
            seguro = nome.replace("\\", "\\\\").replace("'", "\\'")
            r = servico.files().list(
                q=f"name contains '{seguro}' and trashed = false",
                fields="files(name, webViewLink)", pageSize=1, orderBy="modifiedTime desc",
            ).execute()
            return r.get("files", [])
        try:
            arquivos = await asyncio.to_thread(buscar)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui procurar no Drive: {_erro_legivel(exc)}")
        if not arquivos:
            raise ErroFerramenta(f"não achei '{nome}' no seu Drive")
        await asyncio.to_thread(abrir, arquivos[0]["webViewLink"])
        return f"Abri {arquivos[0]['name']} no navegador."

    if memoria is not None:
        memoria.ao_salvar = _sync_automatico

    return [
        Ferramenta("autorizar_google",
                   "Abre o navegador para o usuário autorizar o JARVIS na conta Google dele. "
                   "Use quando outra ferramenta do Google disser que falta autorização.",
                   autorizar_google, resposta_pronta=True),
        Ferramenta("ver_agenda",
                   "Lê os próximos compromissos do Google Agenda do usuário.", ver_agenda,
                   {"dias": {"type": "integer", "description": "Quantos dias olhar à frente, de 1 a 30."}},
                   [], resposta_pronta=True),
        Ferramenta("criar_evento", "Marca um compromisso novo no Google Agenda.", criar_evento,
                   {"titulo": {"type": "string"},
                    "quando": {"type": "string", "description": "Ex.: 'amanhã às 15h', 'sexta 9:30'."},
                    "duracao_min": {"type": "integer", "description": "Duração em minutos (padrão 60)."}},
                   ["titulo", "quando"],
                   perigosa=True,
                   pergunta_confirmacao=lambda a: f"Confirma marcar {a.get('titulo')} para {a.get('quando')}?",
                   resposta_pronta=True),
        Ferramenta("procurar_no_drive", "Procura arquivos no Google Drive do usuário pelo nome.",
                   procurar_no_drive, {"nome": {"type": "string"}}, ["nome"], resposta_pronta=True),
        Ferramenta("abrir_do_drive", "Abre no navegador um arquivo do Google Drive, pelo nome.",
                   abrir_do_drive, {"nome": {"type": "string"}}, ["nome"], resposta_pronta=True),
        Ferramenta("ler_emails",
                   "Lê o Gmail do usuário. Sem busca, pega os não lidos. "
                   "Use busca com a sintaxe do Gmail (ex.: 'from:fulano', 'assunto:fatura').",
                   ler_emails,
                   {"quantidade": {"type": "integer"},
                    "busca": {"type": "string"}},
                   [], resposta_pronta=True),
        Ferramenta("enviar_email",
                   "Envia um e-mail da conta Gmail do usuário.",
                   enviar_email,
                   {"destinatario": {"type": "string"},
                    "assunto": {"type": "string"},
                    "corpo": {"type": "string"}},
                   ["destinatario", "assunto", "corpo"],
                   perigosa=True,
                   pergunta_confirmacao=lambda a: (
                       f"Confirma enviar para {a.get('destinatario')} "
                       f"com assunto '{a.get('assunto')}'?"),
                   resposta_pronta=True),
        Ferramenta("ver_inscricoes_youtube",
                   "Lista os canais em que o usuário está inscrito no YouTube.",
                   ver_inscricoes_youtube,
                   {"quantidade": {"type": "integer"}},
                   [], resposta_pronta=True),
        Ferramenta("restaurar_memoria_do_drive",
                   "Baixa o backup de memória do Drive e substitui a local.",
                   restaurar_memoria_do_drive,
                   perigosa=True,
                   pergunta_confirmacao="Confirma substituir a memória local pela do Drive?",
                   resposta_pronta=True),
    ]
