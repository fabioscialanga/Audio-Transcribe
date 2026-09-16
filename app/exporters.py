from __future__ import annotations

import json
from dataclasses import asdict

from .transcriber import TranscriptionResult


def _timestamp(seconds: float, separator: str = ",") -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def to_srt(result: TranscriptionResult) -> str:
    blocks = []
    for index, segment in enumerate(result.segments, start=1):
        blocks.append(
            f"{index}\n{_timestamp(segment.start)} --> {_timestamp(segment.end)}\n{segment.text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def to_vtt(result: TranscriptionResult) -> str:
    blocks = ["WEBVTT"]
    for segment in result.segments:
        blocks.append(
            f"{_timestamp(segment.start, '.')} --> {_timestamp(segment.end, '.')}\n{segment.text}"
        )
    return "\n\n".join(blocks) + "\n"


def to_json(result: TranscriptionResult) -> str:
    return json.dumps(asdict(result), ensure_ascii=False, indent=2)


def export_content(result: TranscriptionResult, extension: str) -> str:
    extension = extension.lower()
    if extension == ".srt":
        return to_srt(result)
    if extension == ".vtt":
        return to_vtt(result)
    if extension == ".json":
        return to_json(result)
    return result.text
