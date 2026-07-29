from pathlib import Path

import pytest

from nero.config import load_settings


def test_default_settings_are_local() -> None:
    settings = load_settings(Path("settings.toml"))
    assert settings.llm.base_url == "http://127.0.0.1:1234"
    assert settings.audio.frame_samples == 512
    assert settings.audio.input_device_name == "H510-PRO"
    assert settings.stt.model_path.name == "faster-whisper-small"
    assert settings.stt.partial_interval_ms == 0


def test_remote_lm_url_is_rejected(tmp_path: Path) -> None:
    source = Path("settings.toml").read_text(encoding="utf-8")
    path = tmp_path / "settings.toml"
    path.write_text(
        source.replace("http://127.0.0.1:1234", "https://example.com"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="localhost"):
        load_settings(path)
