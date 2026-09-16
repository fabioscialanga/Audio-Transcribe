import wave

from app.whisper_cpp import _convert_to_wav_chunks, _timestamp_ms, parse_whisper_json


def test_timestamp_ms_accepts_srt_and_vtt_separators():
    assert _timestamp_ms("01:02:03,456") == 3_723_456
    assert _timestamp_ms("00:00:07.250") == 7_250


def test_parse_whisper_cpp_full_json():
    payload = {
        "result": {"language": "it"},
        "transcription": [
            {
                "timestamps": {"from": "00:00:00,000", "to": "00:00:01,500"},
                "offsets": {"from": 0, "to": 1500},
                "text": " Ciao mondo",
            },
            {
                "timestamps": {"from": "00:00:01,500", "to": "00:00:03,000"},
                "offsets": {"from": 1500, "to": 3000},
                "text": " Seconda frase",
            },
        ],
    }

    result = parse_whisper_json(payload)

    assert result.text == "Ciao mondo Seconda frase"
    assert result.language == "it"
    assert result.duration == 3.0
    assert result.segments[1].start == 1.5


def test_parse_whisper_cpp_rejects_no_segments_gracefully():
    result = parse_whisper_json({"text": "testo completo", "segments": []})
    assert result.text == "testo completo"
    assert result.segments == []


def test_audio_is_split_into_bounded_wav_chunks(tmp_path):
    source = tmp_path / "source.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(b"\0\0" * (16_000 * 2 + 8_000))

    chunks = _convert_to_wav_chunks(source, tmp_path / "chunks", None, chunk_seconds=1)

    assert [offset for _path, offset in chunks] == [0.0, 1.0, 2.0]
    assert [path.stat().st_size for path, _offset in chunks] == [32_044, 32_044, 16_044]
