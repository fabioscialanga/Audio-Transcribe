from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Callable

import ctranslate2
from faster_whisper import WhisperModel


@dataclass(slots=True)
class TranscriptionOptions:
    engine: str = "whisper_cpp"
    model_name: str = "base"
    language: str | None = None
    task: str = "transcribe"
    initial_prompt: str = ""
    beam_size: int = 5
    vad_filter: bool = True


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = ""
    language_probability: float = 0.0
    duration: float = 0.0
    filtered_repetitions: int = 0


class TranscriptionCancelled(RuntimeError):
    pass


def _normalized_words(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÿ']+", text.casefold())


def trim_repetition_loop(text: str) -> tuple[str, bool]:
    """Cut a phrase when the model repeats the same short block 3+ times."""
    raw_words = text.split()
    normalized = [_normalized_words(word) for word in raw_words]
    words = [parts[0] if parts else word.casefold() for word, parts in zip(raw_words, normalized)]
    if len(words) < 6:
        return text.strip(), False

    for start in range(len(words) - 5):
        max_block = min(12, (len(words) - start) // 3)
        for block_size in range(1, max_block + 1):
            block = words[start : start + block_size]
            if (
                words[start + block_size : start + 2 * block_size] == block
                and words[start + 2 * block_size : start + 3 * block_size] == block
            ):
                clean = " ".join(raw_words[:start]).strip(" ,;:–—-")
                return clean, True
    return text.strip(), False


def detect_compute_device() -> tuple[str, str]:
    """Return the fastest CTranslate2 backend that is usable on this machine."""
    try:
        if ctranslate2.get_cuda_device_count() > 0:
            compute_types = ctranslate2.get_supported_compute_types("cuda")
            if "float16" in compute_types:
                return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


class LocalTranscriber:
    def __init__(self, options: TranscriptionOptions):
        self.options = options
        self.device, self.compute_type = detect_compute_device()

        # Limit model size for systems with limited memory
        model_name = options.model_name
        if self.device == "cpu" and model_name not in ("tiny", "base", "small"):
            # On CPU, limit to smaller models to avoid memory issues
            model_name = "base"

        try:
            self.model = WhisperModel(
                model_name,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=4,  # Limit CPU threads to reduce memory footprint
            )
        except Exception:
            # A driver can expose the GPU even when the CUDA/cuDNN runtime needed by
            # CTranslate2 is incomplete. In that case the app remains usable on CPU.
            if self.device != "cuda":
                raise
            self.device, self.compute_type = "cpu", "int8"
            self.model = WhisperModel(
                options.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )

    def transcribe(
        self,
        file_path: str,
        progress_callback: Callable[[int, float, float], None] | None = None,
        segment_callback: Callable[[TranscriptSegment], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TranscriptionResult:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File non trovato: {file_path}")

        segments, info = self.model.transcribe(
            str(path),
            language=self.options.language,
            task=self.options.task,
            beam_size=max(1, min(self.options.beam_size, 3)),  # Limit beam_size for memory
            best_of=max(1, min(self.options.beam_size, 3)),    # Limit best_of for memory
            temperature=(0.0, 0.2, 0.4),
            repetition_penalty=1.12,
            no_repeat_ngram_size=3,
            vad_filter=self.options.vad_filter,
            vad_parameters={"min_silence_duration_ms": 500},
            word_timestamps=False,
            chunk_length=30,  # Process audio in 30-second chunks
            # This specifically prevents Whisper from carrying a repetition loop
            # from one 30-second window into every following window.
            condition_on_previous_text=False,
            initial_prompt=self.options.initial_prompt or None,
        )

        transcript_segments: list[TranscriptSegment] = []
        filtered_repetitions = 0
        last_normalized = ""
        same_segment_count = 0
        for count, segment in enumerate(segments, start=1):
            if should_cancel and should_cancel():
                raise TranscriptionCancelled("Trascrizione annullata")

            text, repetition_trimmed = trim_repetition_loop(segment.text)
            if repetition_trimmed:
                filtered_repetitions += 1

            normalized = " ".join(_normalized_words(text))
            if normalized and normalized == last_normalized and len(normalized.split()) >= 3:
                same_segment_count += 1
                if same_segment_count >= 2:
                    filtered_repetitions += 1
                    text = ""
            else:
                same_segment_count = 0
            if normalized:
                last_normalized = normalized

            if text:
                item = TranscriptSegment(segment.start, segment.end, text)
                transcript_segments.append(item)
                if segment_callback:
                    segment_callback(item)
            if progress_callback:
                progress_callback(count, segment.end, info.duration)

        return TranscriptionResult(
            text=" ".join(segment.text for segment in transcript_segments).strip(),
            segments=transcript_segments,
            language=info.language or "",
            language_probability=float(info.language_probability or 0.0),
            duration=float(info.duration or 0.0),
            filtered_repetitions=filtered_repetitions,
        )
