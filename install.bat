@echo off

echo,
echo ------------------------------------------------------------------
echo Setup Project
echo ------------------------------------------------------------------
echo,

rem --Download python installer
curl "https://www.python.org/ftp/python/3.10.5/python-3.10.5-amd64.exe" -o python-installer.exe

rem --Install python
python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 

rem --Refresh Environmental Variables
call RefreshEnv.cmd

rem --Use python, pip
python -m venv env
pip install -r requirements.txt
flask run --host=0.0.0.0
flask scheduled

schtasks /create /sc minute /mo 5 /tn "POS Sync" /tr "%cd%\venv\Scripts\flask scheduled"
schtasks /create /sc onstart /tn "POS App" /tr "%cd%\venv\Scripts\flask run --host=0.0.0.0"

echo,
echo ------------------------------------------------------------------
echo Setup Complete
echo ------------------------------------------------------------------
echo,

pause

:: source : https://stackoverflow.com/questions/66913410/install-python-django-in-batch-script

