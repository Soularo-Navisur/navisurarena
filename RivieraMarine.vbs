' NAVISUR — Lanceur silencieux (sans fenetre noire)
' Double-cliquez pour ouvrir NAVISUR directement

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strDir

' Installer les dependances en silence
objShell.Run "cmd /c pip install Flask openpyxl -q 2>nul", 0, True

' Lancer NAVISUR (pythonw = sans fenetre noire de terminal)
objShell.Run "pythonw lancer_bureau.py", 0, False
