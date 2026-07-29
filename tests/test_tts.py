from nero.tts import portuguese_voices


def test_only_portuguese_voices_are_offered() -> None:
    voices = ["af_bella", "pm_santa", "pf_dora", "pm_alex", "bf_emma"]
    assert portuguese_voices(voices) == ["pf_dora", "pm_alex", "pm_santa"]
