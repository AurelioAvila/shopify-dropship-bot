@echo off
cd /d "%~dp0"
rem Terzo brand (Beffante, tech da casa/scrivania). Stesso schema di
rem Groomlyco/Magdock, incluso il retry automatico: il 2026-08-02 la run
rem Magdock e' stata trovata interrotta a forza 2 volte via Task Scheduler
rem (STATUS_CONTROL_C_EXIT) pur girando perfettamente a mano - invece di
rem aspettare il prossimo giro schedulato (giorni dopo), si riprova subito.
rem
rem Interprete del venv con percorso completo, MAI "python" nudo: il Python
rem di sistema non ha le dipendenze del progetto e lo Scheduled Task
rem fallirebbe in silenzio con ModuleNotFoundError (problema gia' capitato
rem davvero su questo repo).
rem
rem Finche' Beffante non ha le credenziali YouTube, generate_buying_guide
rem esce subito con codice 0 senza generare nulla (guardia in cima allo
rem script), quindi questo task non spreca render ne' fa scattare il retry.
".venv\Scripts\python.exe" -m src.jobs.generate_buying_guide --brand beffante >> logs\buying_guide_beffante.log 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [RETRY] primo tentativo fallito con codice %ERRORLEVEL%, riprovo... >> logs\buying_guide_beffante.log
    ".venv\Scripts\python.exe" -m src.jobs.generate_buying_guide --brand beffante >> logs\buying_guide_beffante.log 2>&1
)
