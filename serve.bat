@echo off
cd %~dp0
set FLASK_APP=app.py
call venv\Scripts\flask run --host=0.0.0.0 --port=8080