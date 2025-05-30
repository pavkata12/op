@echo off
REM Run client2 as administrator (background, no console)
set SCRIPT="%~dp0main.py"
set PYTHONW="C:\Users\pavka\AppData\Local\Programs\Python\Python313\pythonw.exe"
powershell -Command "Start-Process -FilePath %PYTHONW% -ArgumentList %SCRIPT% -Verb RunAs" 