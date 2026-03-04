

set DIR=..\ui-control-panel\ui-dashboard
set PORTFOLIO=p107
set KEY_1=u107
set KEY_2=dashboard

wmic process where "name='node.exe' and CommandLine like '%%%KEY_1%%%' and CommandLine like '%%%KEY_2%%%' " get ProcessId | findstr [0-9] >nul

:: for debugging
:: wmic process where "name='node.exe' " get ProcessId,CommandLine

if %errorlevel%==0 (
    echo Web already running for %PORTFOLIO% %KEY_1% %KEY_2%
    echo === Running process ===
    wmic process where "name='node.exe' and CommandLine like '%%%KEY_1%%%' and CommandLine like '%%%KEY_2%%%' " get ProcessId,CommandLine
) else (
    echo Starting bot for %PORTFOLIO%
::  cd ..\..\%SCRIPT%
::  start cmd /k npm run dev
::  cd ..\%DIR% && start cmd /k "npm run dev"
    cd %DIR%
    start cmd /k "npm run dev"
)

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" "http://localhost:7107/"