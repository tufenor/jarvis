"""Upload separado de vídeos de vigilância para o Google Drive.

Usa um token próprio com apenas ``drive.file``. Isso evita misturar o escopo
de upload da vigilância com YouTube, Agenda e a memória do JARVIS.
"""
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DADOS = BASE / "dados"
CREDENCIAIS = DADOS / "google_credenciais.json"
TOKEN = DADOS / "google_drive_seguranca_token.json"
ESCOPO = ["https://www.googleapis.com/auth/drive.file"]
PASTA_PADRAO = "JARVIS - Segurança"


class DriveNaoAutorizado(RuntimeError):
    """Credencial de upload ainda não autorizada."""


def _credenciais(interativo=False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    cred = None
    if TOKEN.is_file():
        try:
            cred = Credentials.from_authorized_user_file(str(TOKEN), ESCOPO)
        except (ValueError, OSError):
            cred = None
    if cred and cred.valid:
        return cred
    if cred and cred.expired and cred.refresh_token:
        cred.refresh(Request())
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        TOKEN.write_text(cred.to_json(), encoding="utf-8")
        return cred
    if not interativo:
        raise DriveNaoAutorizado(
            "Google Drive ainda não autorizado; execute autorizar_google_drive.bat"
        )
    if not CREDENCIAIS.is_file():
        raise DriveNaoAutorizado(
            "falta dados/google_credenciais.json para autorizar o Drive"
        )
    fluxo = InstalledAppFlow.from_client_secrets_file(str(CREDENCIAIS), ESCOPO)
    cred = fluxo.run_local_server(port=0, prompt="consent")
    TOKEN.parent.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(cred.to_json(), encoding="utf-8")
    return cred


def _servico(interativo=False):
    from googleapiclient.discovery import build

    return build(
        "drive", "v3", credentials=_credenciais(interativo), cache_discovery=False
    )


def _pasta(servico, nome):
    seguro = nome.replace("\\", "\\\\").replace("'", "\\'")
    consulta = (
        "mimeType = 'application/vnd.google-apps.folder' and "
        f"name = '{seguro}' and trashed = false"
    )
    encontrados = servico.files().list(
        q=consulta, spaces="drive", fields="files(id,name)", pageSize=10
    ).execute().get("files", [])
    if encontrados:
        return encontrados[0]["id"]
    criada = servico.files().create(
        body={"name": nome, "mimeType": "application/vnd.google-apps.folder"},
        fields="id,name",
    ).execute()
    return criada["id"]


def upload_video(caminho, pasta=PASTA_PADRAO):
    """Envia um vídeo e devolve metadados do arquivo criado."""
    from googleapiclient.http import MediaFileUpload

    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise FileNotFoundError(str(arquivo))
    if arquivo.stat().st_size <= 0:
        raise ValueError("o vídeo está vazio")
    servico = _servico()
    pasta_id = _pasta(servico, pasta)
    media = MediaFileUpload(str(arquivo), mimetype="video/mp4", resumable=True)
    return servico.files().create(
        body={"name": arquivo.name, "parents": [pasta_id]},
        media_body=media,
        fields="id,name,size,createdTime,webViewLink",
    ).execute()


def autorizar():
    """Executa o consentimento interativo uma única vez."""
    _credenciais(interativo=True)
    return TOKEN


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Google Drive do JARVIS")
    parser.add_argument("--autorizar", action="store_true")
    parser.add_argument("--upload")
    args = parser.parse_args()
    if args.autorizar:
        print(f"Token salvo em {autorizar()}")
    elif args.upload:
        resultado = upload_video(args.upload)
        print(f"Enviado: {resultado.get('name')} ({resultado.get('id')})")
    else:
        parser.error("use --autorizar ou --upload CAMINHO")
