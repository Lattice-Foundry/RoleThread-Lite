@echo off
cd /d "%~dp0\..\.."
trainer\Scripts\python.exe -m pytest
pause
