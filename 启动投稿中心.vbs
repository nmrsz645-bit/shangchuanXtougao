Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
venvPython = folder & "\.venv\Scripts\pythonw.exe"
If files.FileExists(venvPython) Then
  pythonw = Chr(34) & venvPython & Chr(34)
Else
  pythonw = "pythonw.exe"
End If
shell.Run pythonw & " " & Chr(34) & folder & "\start_center.py" & Chr(34), 0, False
