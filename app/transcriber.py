from dataclasses import dataclass
from pathlib import Path

import ctranslate2
from faster_whisper import WhisperModel


@dataclass
class TranscriptionOptions:
    model_name: str = "medium"
    language: str = "it"
    initial_prompt: str = ""


class LocalTranscriber:
    def __init__(self, options: TranscriptionOptions):
        self.options = options
        self.device, self.compute_type = self._detect_device()
        self.model = WhisperModel(
            options.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )

    @staticmethod
    def _detect_device():
        try:
            gpu_count = ctranslate2.get_cuda_device_count()
        except Exception:
            gpu_count = 0

        if gpu_count > 0:
            return "cuda", "float16"
        return "cpu", "int8"

    def transcribe(self, file_path: str, progress_callback=None):
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        segments, info = self.model.transcribe(
            str(path),
            language=self.options.language,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True,
            word_timestamps=False,
            condition_on_previous_text=True,
            initial_prompt=self.options.initial_prompt or None,
        )

        chunks = []
        count = 0
        for segment in segments:
            text = segment.text.strip()
            if text:
                chunks.append(text)
            count += 1
            if progress_callback:
                progress_callback(count, segment.end, info.duration)

        return " ".join(chunks).strip(), info
