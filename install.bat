@echo off

cd %~dp0 

rem --Download python installer
curl "https://www.python.org/ftp/python/3.10.5/python-3.10.5-amd64.exe" -o python-installer.exe

rem --Install python
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 

call resetvars.bat

python -m venv venv
call venv\Scripts\activate
pip install -r "requirements.txt"

echo Setup Complete
pause