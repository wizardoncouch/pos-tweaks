Set WshShell = CreateObject("WScript.Shell") 
strPath = Wscript.ScriptFullName
Set objFSO = CreateObject(“Scripting.FileSystemObject”)
Set objFile = objFSO.GetFile(strPath)
strFolder = objFSO.GetParentFolderName(objFile) 

WshShell.Run strFolder & "\script-cron.bat > cron.log", 0
Set WshShell = Nothing