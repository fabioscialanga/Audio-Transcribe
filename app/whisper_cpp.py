from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
from queue import Queue, Empty
from threading import Thread
import subprocess
import tempfile
from typing import Callable
from urllib.request import Request, urlopen
import wave
import zipfile

import av
from av.audio.resampler import AudioResampler

from .transcriber import (
    TranscriptSegment,
    TranscriptionCancelled,
    TranscriptionOptions,
    TranscriptionResult,
)


WHISPER_CPP_VERSION = "v1.9.2"
WHISPER_CPP_ARCHIVE = (
    "https://github.com/ggml-org/whisper.cpp/releases/download/"
    f"{WHISPER_CPP_VERSION}/whisper-blas-bin-x64.zip"
)
WHISPER_CPP_ARCHIVE_SHA256 = "ffe5b47ca8e53a7677949f23a9c4641bbec4eee8a5714c3d14b67bb8d7b24a78"


@dataclass(frozen=True, slots=True)
class ModelAsset:
    filename: str
    size: int
    sha256: str

    @property
    def url(self) -> str:
        return f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{self.filename}"


MODEL_ASSETS = {
    "tiny": ModelAsset(
        "ggml-tiny-q5_1.bin", 32_152_673,
        "818710568da3ca15689e31a743197b520007872ff9576237bda97bd1b469c3d7",
    ),
    "base": ModelAsset(
        "ggml-base-q5_1.bin", 59_707_625,
        "422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898",
    ),
    "small": ModelAsset(
        "ggml-small-q5_1.bin", 190_085_487,
        "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb",
    ),
}

VAD_FILENAME = "ggml-silero-v6.2.0.bin"
VAD_URL = f"https://huggingface.co/ggml-org/whisper-vad/resolve/main/{VAD_FILENAME}"
VAD_SIZE = 885_098
VAD_SHA256 = "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987"

StageCallback = Callable[[str], None]
ProgressCallback = Callable[[int], None]
CancelCallback = Callable[[], bool]


def _run_command(command, cwd, should_cancel=None, on_line=None):
    """Drain output separately so cancellation also works for silent processes."""
    process = subprocess.Popen(
        command, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    lines = Queue(maxsize=256)
    tail = deque(maxlen=12)

    def read_output():
        try:
            for line in process.stdout:
                lines.put(line)
        finally:
            lines.put(None)

    reader = Thread(target=read_output, daemon=True)
    reader.start()
    try:
        while True:
            if should_cancel and should_cancel():
                raise TranscriptionCancelled("Trascrizione annullata")
            try:
                line = lines.get(timeout=0.1)
            except Empty:
                continue
            if line is None:
                break
            tail.append(line)
            if on_line:
                on_line(line)
        while process.poll() is None:
            if should_cancel and should_cancel():
                raise TranscriptionCancelled("Trascrizione annullata")
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
        if process.returncode:
            details = "".join(tail).strip()
            raise RuntimeError(f"whisper.cpp non è riuscito (codice {process.returncode}).\n{details}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        # Drain the bounded queue while the reader completes, including on cancellation.
        while reader.is_alive():
            try:
                lines.get(timeout=0.1)
            except Empty:
                pass
        reader.join()
        process.stdout.close()


def whisper_cpp_cache_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / ".cache"
    return root / "Audio Transcribe" / "whisper.cpp"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(
    url: str,
    destination: Path,
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
    should_cancel: CancelCallback | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = Request(url, headers={"User-Agent": "AudioTranscribe/1.2"})
    try:
        with urlopen(request, timeout=60) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                if should_cancel and should_cancel():
                    raise TranscriptionCancelled("Download annullato")
                output.write(chunk)
        if expected_size is not None and partial.stat().st_size != expected_size:
            raise RuntimeError("Download incompleto: dimensione del file non valida")
        if expected_sha256 and _sha256(partial) != expected_sha256:
            raise RuntimeError("Download non valido: controllo di integrità fallito")
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = (destination / member.filename).resolve()
            if destination_root not in target.parents and target != destination_root:
                raise RuntimeError("Archivio whisper.cpp non valido")
        package.extractall(destination)


def ensure_whisper_cpp(
    stage_callback: StageCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> Path:
    runtime_dir = whisper_cpp_cache_dir() / "bin" / WHISPER_CPP_VERSION
    executable = runtime_dir / "Release" / "whisper-cli.exe"
    if executable.is_file():
        return executable

    if stage_callback:
        stage_callback("Download del motore whisper.cpp…")
    cache_root = whisper_cpp_cache_dir()
    archive = cache_root / "downloads" / f"whisper-cpp-{WHISPER_CPP_VERSION}.zip"
    if not archive.is_file() or _sha256(archive) != WHISPER_CPP_ARCHIVE_SHA256:
        archive.unlink(missing_ok=True)
        _download(
            WHISPER_CPP_ARCHIVE,
            archive,
            expected_sha256=WHISPER_CPP_ARCHIVE_SHA256,
            should_cancel=should_cancel,
        )
    _safe_extract(archive, runtime_dir)
    if not executable.is_file():
        raise RuntimeError("whisper-cli.exe non trovato nel pacchetto scaricato")
    return executable


def ensure_model(
    model_name: str,
    stage_callback: StageCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> Path:
    asset = MODEL_ASSETS.get(model_name)
    if not asset:
        raise ValueError("whisper.cpp supporta i modelli tiny, base e small")
    destination = whisper_cpp_cache_dir() / "models" / asset.filename
    if destination.is_file() and destination.stat().st_size == asset.size:
        return destination
    destination.unlink(missing_ok=True)
    if stage_callback:
        stage_callback(f"Download del modello {model_name} quantizzato…")
    _download(
        asset.url,
        destination,
        expected_sha256=asset.sha256,
        expected_size=asset.size,
        should_cancel=should_cancel,
    )
    return destination


def ensure_vad_model(
    stage_callback: StageCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> Path:
    destination = whisper_cpp_cache_dir() / "models" / VAD_FILENAME
    if destination.is_file() and destination.stat().st_size == VAD_SIZE:
        return destination
    destination.unlink(missing_ok=True)
    if stage_callback:
        stage_callback("Download del filtro silenzi…")
    _download(
        VAD_URL,
        destination,
        expected_sha256=VAD_SHA256,
        expected_size=VAD_SIZE,
        should_cancel=should_cancel,
    )
    return destination


def _timestamp_ms(value: str) -> int:
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})", value.strip())
    if not match:
        return 0
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + millis


def parse_whisper_json(payload: dict) -> TranscriptionResult:
    segments: list[TranscriptSegment] = []
    for raw in payload.get("transcription", payload.get("segments", [])):
        offsets = raw.get("offsets") or {}
        timestamps = raw.get("timestamps") or {}
        start_ms = offsets.get("from")
        end_ms = offsets.get("to")
        if start_ms is None:
            start_ms = _timestamp_ms(str(timestamps.get("from", "")))
        if end_ms is None:
            end_ms = _timestamp_ms(str(timestamps.get("to", "")))
        text = str(raw.get("text", "")).strip()
        if text:
            segments.append(TranscriptSegment(float(start_ms) / 1000, float(end_ms) / 1000, text))

    result_info = payload.get("result") or {}
    language = str(result_info.get("language") or payload.get("language") or "")
    text = " ".join(segment.text for segment in segments).strip()
    if not text:
        text = str(payload.get("text") or "").strip()
    duration = max((segment.end for segment in segments), default=0.0)
    return TranscriptionResult(text=text, segments=segments, language=language, duration=duration)


def _open_wav(path: Path):
    output = wave.open(str(path), "wb")
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(16_000)
    return output


def _convert_to_wav_chunks(
    source: Path,
    destination: Path,
    should_cancel: CancelCallback | None,
    chunk_seconds: int = 15 * 60,
) -> list[tuple[Path, float]]:
    destination.mkdir(parents=True, exist_ok=True)
    chunks: list[tuple[Path, float]] = []
    samples_per_chunk = chunk_seconds * 16_000
    chunk_index = 0
    samples_written = 0
    output_path = destination / f"chunk-{chunk_index:04d}.wav"
    output = _open_wav(output_path)
    try:
        with av.open(str(source)) as container:
            resampler = AudioResampler(format="s16", layout="mono", rate=16_000)

            def write_frame_bytes(data: bytes) -> None:
                nonlocal chunk_index, samples_written, output_path, output
                position = 0
                while position < len(data):
                    remaining_bytes = (samples_per_chunk - samples_written) * 2
                    part = data[position : position + remaining_bytes]
                    output.writeframesraw(part)
                    written = len(part) // 2
                    samples_written += written
                    position += len(part)
                    if samples_written >= samples_per_chunk:
                        output.close()
                        chunks.append((output_path, float(chunk_index * chunk_seconds)))
                        chunk_index += 1
                        samples_written = 0
                        output_path = destination / f"chunk-{chunk_index:04d}.wav"
                        output = _open_wav(output_path)

            for frame in container.decode(audio=0):
                if should_cancel and should_cancel():
                    raise TranscriptionCancelled("Conversione annullata")
                for converted in resampler.resample(frame):
                    write_frame_bytes(converted.to_ndarray().tobytes())
            for converted in resampler.resample(None):
                write_frame_bytes(converted.to_ndarray().tobytes())
    finally:
        output.close()

    if samples_written:
        chunks.append((output_path, float(chunk_index * chunk_seconds)))
    else:
        output_path.unlink(missing_ok=True)
    if not chunks:
        raise RuntimeError("Il file non contiene una traccia audio utilizzabile")
    return chunks


def _offset_result(result: TranscriptionResult, offset: float) -> TranscriptionResult:
    if not offset:
        return result
    result.segments = [
        TranscriptSegment(segment.start + offset, segment.end + offset, segment.text)
        for segment in result.segments
    ]
    result.duration += offset
    return result


class WhisperCppTranscriber:
    device = "whisper.cpp · CPU BLAS"

    def __init__(self, options: TranscriptionOptions):
        self.options = options

    def transcribe(
        self,
        file_path: str,
        progress_callback: Callable[[int, float, float], None] | None = None,
        segment_callback: Callable[[TranscriptSegment], None] | None = None,
        should_cancel: CancelCallback | None = None,
        stage_callback: StageCallback | None = None,
    ) -> TranscriptionResult:
        source = Path(file_path)
        if not source.is_file():
            raise FileNotFoundError(f"File non trovato: {file_path}")

        executable = ensure_whisper_cpp(stage_callback, should_cancel)
        model = ensure_model(self.options.model_name, stage_callback, should_cancel)
        vad_model = ensure_vad_model(stage_callback, should_cancel) if self.options.vad_filter else None

        with tempfile.TemporaryDirectory(prefix="audio-transcribe-") as temp_name:
            temp_dir = Path(temp_name)
            if stage_callback:
                stage_callback("Preparazione dell'audio in blocchi…")
            chunks = _convert_to_wav_chunks(source, temp_dir, should_cancel)
            all_segments: list[TranscriptSegment] = []
            language = ""
            duration = 0.0

            for index, (input_path, offset) in enumerate(chunks):
                if should_cancel and should_cancel():
                    raise TranscriptionCancelled("Trascrizione annullata")
                if stage_callback:
                    stage_callback(f"Trascrizione blocco {index + 1} di {len(chunks)}…")
                output_base = temp_dir / f"transcript-{index:04d}"
                command = [
                    str(executable), "--model", str(model), "--file", str(input_path),
                    "--language", self.options.language or "auto",
                    "--threads", str(max(1, min(6, (os.cpu_count() or 4) - 1))),
                    "--beam-size", str(max(1, min(self.options.beam_size, 5))),
                    "--best-of", str(max(1, min(self.options.beam_size, 5))),
                    "--output-json-full", "--output-file", str(output_base),
                    "--print-progress", "--suppress-nst",
                ]
                if self.options.task == "translate":
                    command.append("--translate")
                if self.options.initial_prompt:
                    command.extend(["--prompt", self.options.initial_prompt])
                if vad_model:
                    command.extend(["--vad", "--vad-model", str(vad_model)])

                def on_line(line):
                    match = re.search(r"progress\s*=\s*(\d+)%", line)
                    if match and progress_callback:
                        local_progress = max(0, min(100, int(match.group(1))))
                        overall = max(1, min(99, int(((index + local_progress / 100) / len(chunks)) * 100)))
                        progress_callback(overall, float(overall), 100.0)

                _run_command(command, executable.parent, should_cancel, on_line)
                output_path = output_base.with_suffix(".json")
                if not output_path.is_file():
                    raise RuntimeError("whisper.cpp non ha prodotto il file di risultato")
                payload = json.loads(output_path.read_text(encoding="utf-8-sig"))
                partial_result = _offset_result(parse_whisper_json(payload), offset)
                language = language or partial_result.language
                duration = max(duration, partial_result.duration)
                all_segments.extend(partial_result.segments)
                for segment in partial_result.segments:
                    if segment_callback:
                        segment_callback(segment)

            return TranscriptionResult(
                text=" ".join(segment.text for segment in all_segments).strip(),
                segments=all_segments,
                language=language,
                duration=duration,
            )
