@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -m src.jobs.generate_buying_guide --brand groomlyco >> logs\buying_guide_groomlyco.log 2>&1
