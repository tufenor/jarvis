# Runbook: qualidade do Tufenor Video

**Responsável:** projeto Tufenor  
**Frequência:** diária e a cada 14 dias  
**Última atualização:** 2026-11-11

## Execução diária

No PowerShell, a partir de `video-archiver-android`:

```powershell
.\scripts\qa_daily.ps1
```

Resultado esperado: `reports\daily-<data>.json` com build e testes aprovados.

Se falhar, não publicar o APK. Guardar a mensagem, corrigir ou abrir uma
ocorrência com o primeiro erro reproduzível.

## Auditoria a cada 14 dias

```powershell
.\scripts\audit_14d.ps1
```

O relatório verifica testes, status do Git, arquivos potencialmente sensíveis,
duplicidade de filas e presença dos documentos de arquitetura. A auditoria
não apaga nada automaticamente.

## Verificação no A53

```powershell
$adb = "$env:LOCALAPPDATA\AndroidTools\platform-tools\adb.exe"
& $adb -d get-state
& $adb -d shell pm path com.tufenor.video
& $adb -d shell monkey -p com.tufenor.video 1
```

Confirmar manualmente: Studio abre, um perfil pode ser trocado, uma fila vazia
é exibida, o histórico não mostra dados de outra conta e o app não registra
`FATAL EXCEPTION`.

## Rollback

Não remover dados do usuário. Instalar o APK anterior com `adb install -r`;
se a mudança alterou o esquema, executar primeiro a migração reversa prevista
no documento da versão. Tokens permanecem no Keystore do perfil.
