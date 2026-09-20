' WOW Legends 플레이어용 런처 실행 (콘솔 창 없이 실행)
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
appPath = scriptDir & "\app.py"

Set shell = CreateObject("WScript.Shell")
cmd = "pythonw.exe """ & appPath & """"
shell.CurrentDirectory = scriptDir
shell.Run cmd, 0, False
