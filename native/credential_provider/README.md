# JARVIS Credential Provider (bloco visual isolado)

Este diretório é separado do aplicativo Python em `jarvis`. O DLL
é um **Credential Provider nativo x64** para o Windows 11. Ele adiciona um tile
com a identidade visual do JARVIS à Logon UI e informa que a voz do aplicativo
começa depois do login.

## Limites intencionais

- O provider não guarda, pede, recebe ou digita senha/PIN.
- `GetSerialization` não produz credencial; o login real continua no Windows
  Hello, PIN, senha ou outro provider já instalado.
- A tela inteira, o fundo e os demais tiles do Winlogon continuam sob controle
  do Windows. O bloco do JARVIS é a parte visual extensível.
- O microfone do desktop seguro não é tratado como o microfone do aplicativo
  Python. O tile não afirma que está escutando quando isso não foi confirmado.

## Compilar

```powershell
Set-Location native\credential_provider
.\build_x64.ps1
```

O resultado é `build\x64\Release\JARVISCredentialProvider.dll`.

## Instalar e remover

Os dois scripts exigem PowerShell elevado. A instalação copia o DLL para
`C:\Program Files\JARVIS\CredentialProvider` e registra uma CLSID própria.

```powershell
.\instalar.ps1
.\remover.ps1
```

Depois de instalar, bloqueie ou reinicie o Windows para a Logon UI recarregar os
providers. Se houver qualquer comportamento estranho, use imediatamente
`remover.ps1` em um PowerShell elevado; Windows Hello/PIN e o login padrão não
são desativados pelo componente.
