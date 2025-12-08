:: start cmd /k "call ..\venv\Scripts\activate && python ..\a339_fx_orchestrator\x13_fx_offline_orch.py"


start cmd /k "cd ..\apps\ui-dashboard && npm run dev"

timeout 10


start cmd /k "cd ..\api && call ..\venv\Scripts\activate && python api.py"


timeout 50

