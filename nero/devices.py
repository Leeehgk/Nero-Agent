from __future__ import annotations

from typing import Any

import pyaudio


def resolve_audio_device(
    audio: pyaudio.PyAudio,
    configured_index: int | None,
    name_contains: str | None,
    *,
    input_device: bool,
    preferred_rate: int,
) -> tuple[int | None, str]:
    """Resolve um dispositivo por índice ou nome, preferindo sua taxa nativa."""
    channel_key = "maxInputChannels" if input_device else "maxOutputChannels"
    default_info = (
        audio.get_default_input_device_info
        if input_device
        else audio.get_default_output_device_info
    )

    if configured_index is not None:
        info = audio.get_device_info_by_index(configured_index)
        if int(info.get(channel_key, 0)) < 1:
            kind = "entrada" if input_device else "saída"
            raise RuntimeError(
                f"O dispositivo {configured_index} não oferece canais de {kind}."
            )
        return configured_index, str(info["name"])

    if name_contains:
        needle = name_contains.casefold()
        matches: list[dict[str, Any]] = []
        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)
            if (
                int(info.get(channel_key, 0)) > 0
                and needle in str(info.get("name", "")).casefold()
            ):
                matches.append(info)
        if not matches:
            kind = "microfone" if input_device else "saída de áudio"
            raise RuntimeError(
                f"{kind.capitalize()} contendo '{name_contains}' não encontrado. "
                "Conecte o headset ou ajuste settings.toml."
            )
        matches.sort(
            key=lambda item: (
                # MME (host API 0) é o backend mais estável para callbacks
                # contínuos nos headsets testados no Windows.
                int(item.get("hostApi", -1)) != 0,
                abs(float(item.get("defaultSampleRate", 0)) - preferred_rate),
                len(str(item.get("name", ""))),
                int(item["index"]),
            )
        )
        selected = matches[0]
        return int(selected["index"]), str(selected["name"])

    info = default_info()
    return int(info["index"]), str(info["name"])
