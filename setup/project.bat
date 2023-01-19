@echo off
cd %~dp0 && cd ..
python -m venv venv
call venv\Scripts\activate
pip install -r "requirements.txt"

set FLASK_APP=app.py && flask run --host=0.0.0.0
set FLASK_APP=app.py && flask scheduled

schtasks /create /sc minute /mo 5 /tn "POS Sync" /tr "set FLASK_APP=app.py && %~dp0\..\venv\Scripts\flask scheduled"
schtasks /create /sc onstart /tn "POS App" /tr "set FLASK_APP=app.py && %~dp0\..\venv\Scripts\flask run --host=0.0.0.0"