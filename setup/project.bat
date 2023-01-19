@echo off
cd %~dp0
python -m venv venv
call venv\Scripts\activate
pip install -r "%~dp0\requirements.txt"

FLASK_APP=app.py flask run --host=0.0.0.0
FLASK_APP=app.py flask scheduled

schtasks /create /sc minute /mo 5 /tn "POS Sync" /tr "FLASK_APP=app.py %~dp0\venv\Scripts\flask scheduled"
schtasks /create /sc onstart /tn "POS App" /tr "FLASK_APP=app.py %~dp0\venv\Scripts\flask run --host=0.0.0.0"