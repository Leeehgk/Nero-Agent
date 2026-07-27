import numpy as np

from nero.stt import LowAudioSignalError


def test_low_audio_signal_error_is_actionable() -> None:
    error = LowAudioSignalError("microfone sem sinal")
    assert "sem sinal" in str(error)


def test_diagnostic_silence_is_below_guard_threshold() -> None:
    audio = np.full(16000, 0.00001, dtype=np.float32)
    centered = audio - float(np.mean(audio))
    rms = float(np.sqrt(np.mean(centered * centered)))
    peak = float(np.max(np.abs(centered)))
    assert rms < 0.0005
    assert peak < 0.003
