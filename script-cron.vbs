Set WshShell = CreateObject("WScript.Shell") 
strCurDir    = WshShell.CurrentDirectory
WshShell.Run chr(34) & strCurDir & "\script-cron.bat" & Chr(34), 0
Set WshShell = Nothing