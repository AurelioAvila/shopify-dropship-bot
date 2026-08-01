@echo off
cd /d "%~dp0"
python -m src.jobs.generate_buying_guide --brand magdock >> logs\buying_guide_magdock.log 2>&1
