from nero.devices import resolve_audio_device


class FakeAudio:
    devices = [
        {
            "index": 2,
            "name": "Headset (H510-PRO)",
            "hostApi": 0,
            "maxInputChannels": 1,
            "maxOutputChannels": 0,
            "defaultSampleRate": 44100.0,
        },
        {
            "index": 17,
            "name": "Headset (H510-PRO)",
            "hostApi": 2,
            "maxInputChannels": 1,
            "maxOutputChannels": 0,
            "defaultSampleRate": 16000.0,
        },
        {
            "index": 4,
            "name": "Fones de ouvido (H510-PRO)",
            "hostApi": 0,
            "maxInputChannels": 0,
            "maxOutputChannels": 2,
            "defaultSampleRate": 44100.0,
        },
        {
            "index": 14,
            "name": "Fones de ouvido (H510-PRO)",
            "hostApi": 2,
            "maxInputChannels": 0,
            "maxOutputChannels": 2,
            "defaultSampleRate": 44100.0,
        },
    ]

    def get_device_count(self) -> int:
        return len(self.devices)

    def get_device_info_by_index(self, index: int) -> dict:
        return self.devices[index]

    def get_default_input_device_info(self) -> dict:
        return self.devices[0]

    def get_default_output_device_info(self) -> dict:
        return self.devices[0]


def test_mme_is_preferred_for_stable_input() -> None:
    index, name = resolve_audio_device(
        FakeAudio(),
        configured_index=None,
        name_contains="H510-PRO",
        input_device=True,
        preferred_rate=16000,
    )
    assert index == 2
    assert name == "Headset (H510-PRO)"


def test_mme_is_preferred_for_kokoro_output() -> None:
    index, name = resolve_audio_device(
        FakeAudio(),
        configured_index=None,
        name_contains="Fones de ouvido (H510-PRO)",
        input_device=False,
        preferred_rate=24000,
    )
    assert index == 4
    assert name == "Fones de ouvido (H510-PRO)"
