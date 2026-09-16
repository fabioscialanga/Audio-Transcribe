from app.exporters import export_content, to_srt, to_vtt
from app.transcriber import TranscriptSegment, TranscriptionResult, trim_repetition_loop


def sample_result():
    return TranscriptionResult(
        text="Ciao mondo Seconda frase",
        segments=[
            TranscriptSegment(0.0, 1.25, "Ciao mondo"),
            TranscriptSegment(61.5, 63.0, "Seconda frase"),
        ],
        language="it",
        language_probability=0.98,
        duration=63.0,
    )


def test_srt_format():
    assert "00:00:00,000 --> 00:00:01,250" in to_srt(sample_result())
    assert "00:01:01,500 --> 00:01:03,000" in to_srt(sample_result())


def test_vtt_format():
    value = to_vtt(sample_result())
    assert value.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:01.250" in value


def test_json_preserves_unicode_and_segments():
    value = export_content(sample_result(), ".json")
    assert '"language": "it"' in value
    assert '"text": "Ciao mondo"' in value


def test_txt_returns_plain_text():
    assert export_content(sample_result(), ".txt") == "Ciao mondo Seconda frase"


def test_repetition_loop_is_removed_entirely_when_it_starts_immediately():
    text = "Sulla informativa Sulla informativa Sulla informativa Sulla informativa"
    cleaned, detected = trim_repetition_loop(text)
    assert detected is True
    assert cleaned == ""


def test_repetition_loop_keeps_the_valid_prefix():
    text = "Questa è la parte valida. rumore di fondo rumore di fondo rumore di fondo"
    cleaned, detected = trim_repetition_loop(text)
    assert detected is True
    assert cleaned == "Questa è la parte valida."


def test_normal_text_is_not_modified():
    text = "Questa è una frase normale che non contiene alcun ciclo ripetitivo."
    assert trim_repetition_loop(text) == (text, False)
