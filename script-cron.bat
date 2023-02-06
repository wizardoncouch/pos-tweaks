@echo off
cd %~dp0
set FLASK_APP=app.py
call venv\Scripts\flask sync
@REM NET STOP eOne.SmartConnect.WindowsService.exe
@REM NET START eOne.SmartConnect.WindowsService.exe