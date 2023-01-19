@echo off

call flask run --host=0.0.0.0
call flask scheduled

schtasks /create /sc minute /mo 5 /tn "POS Sync" /tr "flask scheduled"
schtasks /create /sc onstart /tn "POS App" /tr "flask run --host=0.0.0.0"