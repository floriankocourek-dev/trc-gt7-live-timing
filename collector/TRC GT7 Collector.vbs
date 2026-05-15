Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
pythonw = folder & "\.venv\Scripts\pythonw.exe"
script = folder & "\start_collector_gui.pyw"
If fso.FileExists(pythonw) Then
  shell.Run Chr(34) & pythonw & Chr(34) & " " & Chr(34) & script & Chr(34), 0, False
Else
  MsgBox "Collector Python environment was not found. Please run the setup once or use the packaged EXE.", 16, "TRC GT7 Collector"
End If

