# Audio Transcribe

Applicazione desktop Windows per trascrivere e tradurre file audio/video in modo
accurato e completamente locale. Nessun file viene caricato online.

## Funzionalità

- drag & drop di audio e video;
- trascrizione locale con `faster-whisper`;
- rilevamento automatico della lingua o selezione manuale;
- traduzione diretta in inglese;
- rilevamento GPU NVIDIA con fallback CPU;
- testo mostrato in tempo reale e modificabile;
- glossario contestuale, beam search regolabile e filtro dei silenzi;
- annullamento della trascrizione;
- esportazione in TXT, SRT, WebVTT e JSON;
- preferenze memorizzate tra un avvio e l'altro;
- nessuna dipendenza da FFmpeg installato nel sistema (PyAV è incluso).
- download dei modelli compatibile con il trust store certificati di Windows.

Formati principali: MP3, WAV, M4A, AAC, FLAC, OGG, OPUS, MP4, MOV, MKV,
WEBM, AVI, MPEG e MPG.

## Avvio per lo sviluppo

È consigliato Python 3.11 x64 su Windows 10 o 11.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Al primo utilizzo viene scaricato soltanto il modello Whisper selezionato. Il
modello `small` è il compromesso consigliato; `large-v3` offre la qualità più
alta, ma richiede più memoria e tempo, soprattutto su CPU.

## Creare i pacchetti Windows

```powershell
.\build_windows.ps1
```

Lo script crea:

- `dist\AudioTranscribe-portable-win64.zip`, versione portabile;
- `dist\installer\AudioTranscribe-Setup-1.1.1.exe`, installer per utente se
  [Inno Setup 6](https://jrsoftware.org/isinfo.php) è installato.

L'installer non richiede privilegi di amministratore e aggiunge il collegamento
al menu Start. I modelli non vengono incorporati, mantenendo ragionevole la
dimensione del download.
