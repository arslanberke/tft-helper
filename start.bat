@echo off
REM TFT Advisor - one-click start.
REM Creates the venv + installs deps on first run, then starts the service.
REM `start.bat --install-only` runs the setup steps and exits (used by install.bat).
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo [setup] creating virtualenv...
  py -3 -m venv .venv || python -m venv .venv
  echo [setup] installing service + local model + scout deps (first run takes a while)...
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -e ".[laya,scout]"
  echo [setup] fetching champion icons for the scout...
  .venv\Scripts\python -m service.scripts.fetch_champ_icons
  echo [setup] done. Next runs skip this.
)

if /i "%~1"=="--install-only" exit /b 0

echo [tft-advisor] starting on http://127.0.0.1:8371 ...
echo Optional env vars: TYPESAFE_API_KEY (Jev), KEV_URL (local Kev), TFT_SCOUT=0
.venv\Scripts\tft-advisor
