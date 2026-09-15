# Audio Transcribe

Windows desktop app per trascrivere rapidamente file audio in testo, con priorità alla fedeltà della trascrizione.

## MVP

- Drag & drop di file audio/video
- Trascrizione locale con faster-whisper
- Rilevamento automatico GPU NVIDIA con fallback CPU
- Visualizzazione del testo trascritto
- Copia negli appunti
- Export in file .txt
- Nessun upload cloud: elaborazione locale

## Formati supportati

MP3, WAV, M4A, AAC, FLAC, OGG, MP4, MOV, MKV.

## Requisiti

- Windows 10/11
- Python 3.11 consigliato
- FFmpeg disponibile nel PATH
- GPU NVIDIA opzionale

## Avvio

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Al primo utilizzo faster-whisper scarica il modello selezionato.

## Note sulla qualità

L'app usa per default il modello `large-v3` quando è disponibile una GPU NVIDIA e `medium` su CPU. Puoi cambiare il modello dall'interfaccia.

Per privilegiare la fedeltà:
- lingua italiana impostata esplicitamente
- beam search
- VAD
- temperatura 0
- contextual prompt opzionale per termini tecnici
