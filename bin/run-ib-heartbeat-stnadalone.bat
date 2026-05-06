@echo off

set PROGRAM=python.exe
set PORTFOLIO_ID=p107
set KEY_1=ib_heartbeat_monitor_standalone
set KEY_2=p107

set CMD="call ..\.venv\Scripts\activate && python ..\utils\ib_heartbeat_monitor_standalone.py --portfolio-id=%PORTFOLIO_ID%"
rem set CMD="call ..\.venv\Scripts\activate ; python ..\utils\ib_heartbeat_monitor_standalone.py --portfolio-id=%PORTFOLIO_ID%"

wmic process where "name='%PROGRAM%' and CommandLine like '%%%KEY_1%%%' and CommandLine like '%%%KEY_2%%%' " get ProcessId | findstr [0-9] >nul

:: for debugging
:: wmic process where "name='node.exe' " get ProcessId,CommandLine

if %errorlevel%==0 (
    echo We already running for %PROGRAM% %KEY_1% %KEY_2% %CMD%
    echo === Running process ===
    wmic process where "name='%PROGRAM%' and CommandLine like '%%%KEY_1%%%' and CommandLine like '%%%KEY_2%%%' " get ProcessId,CommandLine
) else (
    echo Starting program %CMD%
    start cmd /k %CMD%

    rem %CMD%
)

:: start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" "http://localhost:51071/"