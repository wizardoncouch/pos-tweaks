@echo off
call %~dp0\setup\install.bat
call %~dp0\setup\requirements.bat
call %~dp0\setup\project.bat
echo Setup Complete
pause