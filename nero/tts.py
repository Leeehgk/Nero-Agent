from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Callable

from kokoro_onnx import Kokoro
import numpy as np
import onnxruntime as ort
import pyaudio

from nero.config import AudioSettings, TTSSettings
from nero.devices import resolve_audio_device


def portuguese_voices(voices: list[str]) -> list[str]:
    """Retorna somente as vozes treinadas para português."""
    return sorted(voice for voice in voices if voice.startswith(("pf_", "pm_")))


class AudioPlayer:
    def __init__(self, settings: AudioSettings) -> None:
        self._audio = pyaudio.PyAudio()
        self.output_device, self.output_device_name = resolve_audio_device(
            self._audio,
            settings.output_device,
            settings.output_device_name,
            input_device=False,
            preferred_rate=24000,
        )
        self._stream: pyaudio.Stream | None = None
        self._sample_rate: int | None = None
        self._lock = threading.Lock()

    def play(
        self,
        samples: np.ndarray,
        sample_rate: int,
        cancel: threading.Event,
        on_first_write: Callable[[], None],
    ) -> bool:
        with self._lock:
            if self._stream is None or self._sample_rate != sample_rate:
                if self._stream:
                    self._stream.close()
                self._stream = self._audio.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=sample_rate,
                    output=True,
                    output_device_index=self.output_device,
                    frames_per_buffer=max(1, sample_rate // 50),
                )
                self._sample_rate = sample_rate

            block_size = max(1, sample_rate // 50)
            started = False
            samples = np.asarray(samples, dtype=np.float32)
            for start in range(0, len(samples), block_size):
                if cancel.is_set():
                    return False
                if not started:
                    started = True
                    on_first_write()
                block = samples[start : start + block_size]
                self._stream.write(block.tobytes(), exception_on_underflow=False)
            return True

    def close(self) -> None:
        with self._lock:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._audio.terminate()


class SpeechSynthesizer:
    def __init__(
        self,
        settings: TTSSettings,
        audio_settings: AudioSettings,
    ) -> None:
        self.settings = settings
        self.player = AudioPlayer(audio_settings)
        self._kokoro: Kokoro | None = None
        self._voice = settings.voice
        self._voices: list[str] = []

    def start(self) -> None:
        missing = [
            path
            for path in (self.settings.model_path, self.settings.voices_path)
            if not path.exists()
        ]
        if missing:
            raise RuntimeError(
                "Arquivos do Kokoro ausentes: "
                + ", ".join(str(path) for path in missing)
                + ". Execute: py -3.11 setup_models.py"
            )
        # Kokoro permanece explicitamente na CPU. Isso evita disputar VRAM
        # com o LLM e contorna falhas de ConvTranspose do DirectML no Windows.
        session = ort.InferenceSession(
            str(self.settings.model_path),
            providers=["CPUExecutionProvider"],
        )
        self._kokoro = Kokoro.from_session(
            session,
            str(self.settings.voices_path),
        )
        self._voices = portuguese_voices(self._kokoro.get_voices())
        if self._voice not in self._voices:
            raise RuntimeError(f"Voz Kokoro PT-BR desconhecida: {self._voice}")

    @property
    def voice(self) -> str:
        return self._voice

    @property
    def voices(self) -> tuple[str, ...]:
        return tuple(self._voices)

    def set_voice(self, voice: str) -> None:
        if voice not in self._voices:
            raise ValueError(f"Voz PT-BR indisponível: {voice}")
        self._voice = voice

    async def warmup(self) -> None:
        if self._kokoro is None:
            raise RuntimeError("Kokoro não inicializado")
        await asyncio.to_thread(
            self._kokoro.create,
            "Pronto para conversar.",
            self._voice,
            self.settings.speed,
            self.settings.language,
        )

    async def speak(
        self,
        text: str,
        cancel: threading.Event,
        on_first_pcm: Callable[[], None],
        on_first_audio: Callable[[], None],
    ) -> bool:
        if self._kokoro is None:
            raise RuntimeError("Kokoro não inicializado")
        voice = self._voice
        first_pcm = True
        first_audio = True
        async for samples, sample_rate in self._kokoro.create_stream(
            text,
            voice,
            self.settings.speed,
            self.settings.language,
        ):
            if cancel.is_set():
                return False
            if first_pcm:
                first_pcm = False
                on_first_pcm()

            def mark_audio() -> None:
                nonlocal first_audio
                if first_audio:
                    first_audio = False
                    on_first_audio()

            completed = await asyncio.to_thread(
                self.player.play,
                samples,
                sample_rate,
                cancel,
                mark_audio,
            )
            if not completed:
                return False
        return True

    def close(self) -> None:
        self.player.close()
