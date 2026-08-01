@echo off
cd /d "%~dp0"
python -m src.jobs.daily_promo --count 6 >> logs\daily_promo.log 2>&1
