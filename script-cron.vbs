Set WshShell = CreateObject("WScript.Shell") 
strPath = Wscript.ScriptFullName
Set objFSO = CreateObject(“Scripting.FileSystemObject”)
Set objFile = objFSO.GetFile(strPath)
strFolder = objFSO.GetParentFolderName(objFile) 

WshShell "cd " & strFolder & " && set FLASK_APP=app.py && venv\Scripts\flask scheduled > " & strFolder & "\cron.log"

Set WshShell = Nothing