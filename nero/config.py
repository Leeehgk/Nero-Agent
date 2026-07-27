from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
import tomllib
from urllib.parse import urlparse


@dataclass(frozen=True)
class LLMSettings:
    base_url: str
    model: str
    fallback_model: str
    context_length: int
    max_output_tokens: int
    temperature: float
    top_p: float
    repeat_penalty: float
    auto_fallback: bool


@dataclass(frozen=True)
class STTSettings:
    model_path: Path
    fallback_model_path: Path
    cpu_threads: int
    partial_interval_ms: int
    final_beam_size: int


@dataclass(frozen=True)
class TTSSettings:
    model_path: Path
    voices_path: Path
    voice: str
    language: str
    speed: float


@dataclass(frozen=True)
class AudioSettings:
    input_device: int | None
    output_device: int | None
    input_device_name: str | None
    output_device_name: str | None
    sample_rate: int
    frame_samples: int
    vad_threshold: float
    min_speech_ms: int
    end_silence_ms: int
    barge_in_ms: int
    pre_roll_ms: int


@dataclass(frozen=True)
class AppSettings:
    root: Path
    log_path: Path
    llm: LLMSettings
    stt: STTSettings
    tts: TTSSettings
    audio: AudioSettings
    target_p50_ms: int
    target_p95_ms: int


def _path(root: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else root / candidate


def _device(value: int) -> int | None:
    return None if value < 0 else value


def _assert_loopback(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("llm.base_url deve ser uma URL HTTP válida")
    hostname = parsed.hostname.lower()
    if hostname == "localhost":
        return
    try:
        if ip_address(hostname).is_loopback:
            return
    except ValueError:
        pass
    raise ValueError("Por segurança, llm.base_url deve apontar para localhost")


def load_settings(path: Path) -> AppSettings:
    path = path.resolve()
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    root = path.parent
    llm = data["llm"]
    stt = data["stt"]
    tts = data["tts"]
    audio = data["audio"]
    latency = data["latency"]
    base_url = llm["base_url"].rstrip("/")
    _assert_loopback(base_url)

    settings = AppSettings(
        root=root,
        log_path=_path(root, data["app"]["log_path"]),
        llm=LLMSettings(
            base_url=base_url,
            model=llm["model"],
            fallback_model=llm["fallback_model"],
            context_length=int(llm["context_length"]),
            max_output_tokens=int(llm["max_output_tokens"]),
            temperature=float(llm["temperature"]),
            top_p=float(llm["top_p"]),
            repeat_penalty=float(llm["repeat_penalty"]),
            auto_fallback=bool(llm.get("auto_fallback", True)),
        ),
        stt=STTSettings(
            model_path=_path(root, stt["model_path"]),
            fallback_model_path=_path(root, stt["fallback_model_path"]),
            cpu_threads=int(stt["cpu_threads"]),
            partial_interval_ms=int(stt["partial_interval_ms"]),
            final_beam_size=int(stt.get("final_beam_size", 1)),
        ),
        tts=TTSSettings(
            model_path=_path(root, tts["model_path"]),
            voices_path=_path(root, tts["voices_path"]),
            voice=tts["voice"],
            language=tts["language"],
            speed=float(tts["speed"]),
        ),
        audio=AudioSettings(
            input_device=_device(int(audio["input_device"])),
            output_device=_device(int(audio["output_device"])),
            input_device_name=audio.get("input_device_name") or None,
            output_device_name=audio.get("output_device_name") or None,
            sample_rate=int(audio["sample_rate"]),
            frame_samples=int(audio["frame_samples"]),
            vad_threshold=float(audio["vad_threshold"]),
            min_speech_ms=int(audio["min_speech_ms"]),
            end_silence_ms=int(audio["end_silence_ms"]),
            barge_in_ms=int(audio["barge_in_ms"]),
            pre_roll_ms=int(audio["pre_roll_ms"]),
        ),
        target_p50_ms=int(latency["target_p50_ms"]),
        target_p95_ms=int(latency["target_p95_ms"]),
    )
    _validate(settings)
    return settings


def _validate(settings: AppSettings) -> None:
    if settings.llm.context_length < 1024:
        raise ValueError("context_length deve ser pelo menos 1024")
    if settings.audio.sample_rate != 16000:
        raise ValueError("Silero e Whisper exigem áudio de entrada a 16 kHz")
    if settings.audio.frame_samples != 512:
        raise ValueError("Silero VAD exige frames de 512 amostras a 16 kHz")
    if not 0 < settings.audio.vad_threshold < 1:
        raise ValueError("vad_threshold deve estar entre 0 e 1")
    if not 1 <= settings.stt.final_beam_size <= 5:
        raise ValueError("stt.final_beam_size deve estar entre 1 e 5")
    if settings.tts.language.lower() != "pt-br":
        raise ValueError("A v1 foi calibrada para TTS pt-br")
