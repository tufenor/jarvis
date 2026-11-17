' Abre o JARVIS sem janela de terminal, no login do Windows.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\JARVIS"
shell.Run """C:\JARVIS\.venv\Scripts\pythonw.exe"" -m jarvis", 0, False
