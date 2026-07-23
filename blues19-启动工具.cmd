@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  start "" pyw -3 "%~dp0blues19-app.py"
) else if exist "%LocalAppData%\Programs\Python\Python312\pythonw.exe" (
  start "" "%LocalAppData%\Programs\Python\Python312\pythonw.exe" "%~dp0blues19-app.py"
) else (
  start "" pythonw "%~dp0blues19-app.py"
)
