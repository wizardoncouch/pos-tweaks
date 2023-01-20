@echo off
cd %~dp0 
python -m venv venv
call venv\Scripts\activate
pip install -r "requirements.txt"

schtasks /create /sc minute /mo 5 /tn "POS Sync" /tr "%~dp0\cron.bat"
schtasks /create /sc onstart /tn "POS App" /tr "%~dp0\serve.bat"

echo Setup Complete
pause