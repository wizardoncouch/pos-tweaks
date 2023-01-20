@echo off

rem --Download python installer
curl "https://www.python.org/ftp/python/3.10.5/python-3.10.5-amd64.exe" -o python-installer.exe

rem --Install python
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 

@”%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe” -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command “[System.Net.ServicePointManager]::SecurityProtocol = 3072; iex ((New-Object System.Net.WebClient).DownloadString(‘https://community.chocolatey.org/install.ps1’))” && SET “PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin”
resetvars

cd %~dp0 
python -m venv venv
call venv\Scripts\activate
pip install -r "requirements.txt"

schtasks /create /sc minute /mo 5 /tn "POS Sync" /tr "%~dp0\cron.bat"
schtasks /create /sc onstart /tn "POS App" /tr "%~dp0\serve.bat"

echo Setup Complete
pause