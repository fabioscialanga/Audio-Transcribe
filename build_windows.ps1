param(
    [switch]$SkipInstaller,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-InnoSetup {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $locations = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($location in $locations) {
        if (Test-Path -LiteralPath $location) { return $location }
    }
    return $null
}

if (-not (Test-Path -LiteralPath ".venv")) {
    Write-Host "Creazione ambiente di build..."
    py -3.11 -m venv .venv
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Ambiente Python non valido. Installa Python 3.11 x64 e riprova."
}

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Comando Python non riuscito (codice $LASTEXITCODE)."
    }
}

Write-Host "Installazione dipendenze di build..."
Invoke-Python -m pip install --upgrade pip --use-feature=truststore
Invoke-Python -m pip install -r requirements-build.txt --use-feature=truststore
if (-not $SkipTests) {
    Invoke-Python -m pip install pytest --use-feature=truststore
    Invoke-Python -m pytest -q
}

Invoke-Python tools\create_icon.py

Write-Host "Creazione applicazione Windows..."
Invoke-Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "AudioTranscribe" `
    --icon "assets\icon.ico" `
    --add-data "assets\icon.svg;assets" `
    --collect-all ctranslate2 `
    --collect-all faster_whisper `
    --collect-all tokenizers `
    --collect-all av `
    main.py

$portablePath = Join-Path $PSScriptRoot "dist\AudioTranscribe-portable-win64.zip"
if (Test-Path -LiteralPath $portablePath) {
    Remove-Item -LiteralPath $portablePath -Force
}
Compress-Archive -Path "dist\AudioTranscribe\*" -DestinationPath $portablePath -CompressionLevel Optimal
Write-Host "Pacchetto portabile: $portablePath"

if (-not $SkipInstaller) {
    $iscc = Find-InnoSetup
    if ($iscc) {
        Write-Host "Creazione installer Windows..."
        & $iscc "installer\AudioTranscribe.iss"
        if ($LASTEXITCODE -ne 0) { throw "Creazione installer non riuscita." }
        Write-Host "Installer: dist\installer\AudioTranscribe-Setup-1.2.0.exe"
    } else {
        Write-Warning "Inno Setup 6 non trovato: creato solo il pacchetto portabile."
        Write-Warning "Installa Inno Setup 6 e riesegui lo script per ottenere il setup .exe."
    }
}

Write-Host "Build completata."
