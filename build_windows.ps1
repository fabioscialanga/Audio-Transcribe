$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --clean --windowed --name "AudioTranscribe" main.py

Write-Host ""
Write-Host "Build completata: dist\AudioTranscribe\AudioTranscribe.exe"
