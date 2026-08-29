Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "cmd.exe /c cd /d " & Q(root) & " && set PYTHONPATH=" & Q(root & "\app") & " && pythonw -m desktop_posting.main --base-dir " & Q(root & "\.") & " --auto-start"
shell.Run cmd, 0, False

Function Q(value)
  Q = Chr(34) & value & Chr(34)
End Function
