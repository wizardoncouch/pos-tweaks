@echo off
cd %~dp0
call venv\Scripts\python sync.py files
NET STOP ApacheHTTPServer
NET START ApacheHTTPServer