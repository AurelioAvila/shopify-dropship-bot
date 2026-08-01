@echo off
cd /d "%~dp0"
python fix_missing_youtube.py >> logs\fix_youtube.log 2>&1
