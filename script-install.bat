@echo off

rem --Download python installer
curl "https://www.python.org/ftp/python/3.10.5/python-3.10.5-amd64.exe" -o python-installer.exe

rem --Install python
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 

call %~dp0\~resetvars.bat

cd %~dp0 
python -m venv venv
call venv\Scripts\activate
pip install -r "requirements.txt"

schtasks /create /sc minute /mo 5 /tn "POS Sync" /tr "%~dp0\script-cron.bat"
schtasks /create /sc onstart /tn "POS App" /tr "%~dp0\script-serve.bat"

echo Setup Complete
pause