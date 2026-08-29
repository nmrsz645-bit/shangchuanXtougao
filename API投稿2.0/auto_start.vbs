Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "cmd.exe /c cd /d " & Q(root) & " && start_auto.bat"
shell.Run cmd, 0, False

Function Q(value)
  Q = Chr(34) & value & Chr(34)
End Function
