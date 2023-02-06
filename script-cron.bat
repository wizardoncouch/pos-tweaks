@echo off
cd %~dp0
set FLASK_APP=app.py
call venv\Scripts\flask sync
NET STOP ApacheHTTPServer
NET START ApacheHTTPServer