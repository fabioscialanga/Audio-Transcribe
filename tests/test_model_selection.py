from unittest.mock import Mock

from app import transcriber


def test_cpu_does_not_silently_replace_selected_model(monkeypatch):
    monkeypatch.setattr(transcriber, "detect_compute_device", lambda: ("cpu", "int8"))
    model = Mock()
    monkeypatch.setattr(transcriber, "WhisperModel", model)
    transcriber.LocalTranscriber(transcriber.TranscriptionOptions(model_name="medium"))
    assert model.call_args.args == ("medium",)
    assert model.call_args.kwargs["device"] == "cpu"
