Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
shell.Run "pythonw.exe " & Chr(34) & folder & "\start_center.py" & Chr(34), 0, False
