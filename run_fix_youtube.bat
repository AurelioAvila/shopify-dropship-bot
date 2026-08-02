@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" fix_missing_youtube.py >> logs\fix_youtube.log 2>&1
