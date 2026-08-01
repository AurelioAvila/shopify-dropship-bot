@echo off
cd /d "%~dp0"
python -m src.jobs.generate_buying_guide --brand groomlyco >> logs\buying_guide_groomlyco.log 2>&1
