from pathlib import Path
import math

from nero.audio import EndpointTracker
from nero.config import load_settings


def test_endpoint_and_barge_in_decisions() -> None:
    settings = load_settings(Path("settings.toml")).audio
    tracker = EndpointTracker(settings)

    assert tracker.process(0.9, False) == "speech_candidate"
    assert tracker.process(0.9, False) == "speech_candidate"
    assert tracker.process(0.9, False) == "speech_start"

    silence_frames = math.ceil(settings.end_silence_ms / tracker.frame_ms)
    for _ in range(silence_frames - 1):
        assert tracker.process(0.1, False) == "speech_silence"
    assert tracker.process(0.1, False) == "utterance_end"

    tracker.reset()
    for _ in range(3):
        assert tracker.process(0.9, True) == "speech_candidate"
    assert tracker.process(0.9, True) == "barge_in"
