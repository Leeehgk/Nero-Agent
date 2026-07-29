from pathlib import Path
import math

from nero.audio import EndpointTracker, MicrophoneEngine
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


def test_microphone_falls_back_to_mme_after_transient_host_errors() -> None:
    class FakeAudio:
        def __init__(self) -> None:
            self.opened: list[int] = []
            self.devices = [
                {
                    "index": 2,
                    "name": "Headset (H510-PRO)",
                    "hostApi": 0,
                    "maxInputChannels": 1,
                },
                {
                    "index": 17,
                    "name": "Headset (H510-PRO)",
                    "hostApi": 2,
                    "maxInputChannels": 1,
                },
            ]

        def open(self, **kwargs):
            index = kwargs["input_device_index"]
            self.opened.append(index)
            if len(self.opened) <= 3:
                raise OSError(-9999, "Unanticipated host error")
            return object()

        def get_device_count(self) -> int:
            return len(self.devices)

        def get_device_info_by_index(self, index: int) -> dict:
            return self.devices[index]

    engine = MicrophoneEngine.__new__(MicrophoneEngine)
    engine.settings = load_settings(Path("settings.toml")).audio
    engine.input_device = 17
    engine.input_device_name = "Headset (H510-PRO)"
    engine._audio = FakeAudio()

    stream = engine._open_input_stream(lambda *_: None)

    assert stream is not None
    assert engine._audio.opened == [17, 17, 17, 2]
    assert engine.input_device == 2
