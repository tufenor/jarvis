"""Autoriza o upload de vídeos do JARVIS no Google Drive."""
from google_drive_upload import autorizar


if __name__ == "__main__":
    print("Uma janela do Google será aberta; aceite apenas na sua conta.")
    print(f"Token salvo em {autorizar()}")
