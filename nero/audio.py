from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import queue
import threading
import time
from typing import Callable

from faster_whisper.vad import get_vad_model
import numpy as np
import pyaudio

from nero.config import AudioSettings
from nero.devices import resolve_audio_device


@dataclass(frozen=True)
class CapturedUtterance:
    audio: np.ndarray
    speech_end: float


class EndpointTracker:
    def __init__(self, settings: AudioSettings) -> None:
        self.frame_ms = settings.frame_samples * 1000 / settings.sample_rate
        self.threshold = settings.vad_threshold
        self.min_speech_ms = settings.min_speech_ms
        self.end_silence_ms = settings.end_silence_ms
        self.barge_in_ms = settings.barge_in_ms
        self.speaking = False
        self.speech_ms = 0.0
        self.silence_ms = 0.0

    def process(self, probability: float, playback_active: bool) -> str:
        if probability >= self.threshold:
            self.speech_ms += self.frame_ms
            self.silence_ms = 0.0
            if not self.speaking:
                required = self.barge_in_ms if playback_active else self.min_speech_ms
                if self.speech_ms >= required:
                    self.speaking = True
                    return "barge_in" if playback_active else "speech_start"
                return "speech_candidate"
            return "speech"

        self.speech_ms = 0.0
        if not self.speaking:
            self.silence_ms = 0.0
            return "silence"
        self.silence_ms += self.frame_ms
        if self.silence_ms >= self.end_silence_ms:
            self.speaking = False
            self.silence_ms = 0.0
            return "utterance_end"
        return "speech_silence"

    def reset(self) -> None:
        self.speaking = False
        self.speech_ms = 0.0
        self.silence_ms = 0.0


class MicrophoneEngine:
    def __init__(
        self,
        settings: AudioSettings,
        on_utterance: Callable[[CapturedUtterance], None],
        on_partial: Callable[[np.ndarray], None],
        on_barge_in: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self.settings = settings
        self.on_utterance = on_utterance
        self.on_partial = on_partial
        self.on_barge_in = on_barge_in
        self.on_error = on_error
        self._audio = pyaudio.PyAudio()
        self.input_device, self.input_device_name = resolve_audio_device(
            self._audio,
            settings.input_device,
            settings.input_device_name,
            input_device=True,
            preferred_rate=settings.sample_rate,
        )
        self._stream: pyaudio.Stream | None = None
        self._frames: queue.Queue[tuple[np.ndarray, float]] = queue.Queue(maxsize=64)
        self._stop = threading.Event()
        self._enabled = threading.Event()
        self._enabled.set()
        self._playback = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, partial_interval_ms: int) -> None:
        self._partial_interval_ms = partial_interval_ms

        def callback(in_data, frame_count, time_info, status_flags):
            if self._enabled.is_set():
                frame = np.frombuffer(in_data, dtype=np.int16).astype(np.float32)
                frame /= 32768.0
                item = (frame, time.perf_counter())
                try:
                    self._frames.put_nowait(item)
                except queue.Full:
                    try:
                        self._frames.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._frames.put_nowait(item)
                    except queue.Full:
                        pass
            return (None, pyaudio.paContinue)

        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.settings.sample_rate,
            input=True,
            input_device_index=self.input_device,
            frames_per_buffer=self.settings.frame_samples,
            stream_callback=callback,
            start=False,
        )
        self._thread = threading.Thread(
            target=self._worker, name="nero-vad", daemon=True
        )
        self._thread.start()
        self._stream.start_stream()

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._enabled.set()
        else:
            self._enabled.clear()
            self._drain_frames()

    def set_playback_active(self, active: bool) -> None:
        if active:
            self._playback.set()
        else:
            self._playback.clear()

    def close(self) -> None:
        self._stop.set()
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)
        self._audio.terminate()

    def _worker(self) -> None:
        try:
            vad = get_vad_model()
            tracker = EndpointTracker(self.settings)
            vad_window: deque[np.ndarray] = deque(
                [np.zeros(self.settings.frame_samples, dtype=np.float32)] * 2,
                maxlen=3,
            )
            pre_roll_frames = max(
                1,
                round(
                    self.settings.pre_roll_ms
                    * self.settings.sample_rate
                    / 1000
                    / self.settings.frame_samples
                ),
            )
            pre_roll: deque[np.ndarray] = deque(maxlen=pre_roll_frames)
            utterance: list[np.ndarray] = []
            last_speech_time = time.perf_counter()
            last_partial_samples = 0

            while not self._stop.is_set():
                try:
                    frame, frame_time = self._frames.get(timeout=0.1)
                except queue.Empty:
                    continue
                vad_window.append(frame)
                probabilities = vad(np.concatenate(tuple(vad_window)))
                probability = float(probabilities.reshape(-1)[-1])
                pre_roll.append(frame)
                event = tracker.process(probability, self._playback.is_set())

                if probability >= self.settings.vad_threshold:
                    last_speech_time = frame_time

                if event in {"speech_start", "barge_in"}:
                    utterance = list(pre_roll)
                    last_partial_samples = len(utterance) * self.settings.frame_samples
                    if event == "barge_in":
                        self.on_barge_in()
                elif tracker.speaking:
                    utterance.append(frame)

                samples = len(utterance) * self.settings.frame_samples
                interval_samples = int(
                    self._partial_interval_ms * self.settings.sample_rate / 1000
                )
                if (
                    tracker.speaking
                    and samples - last_partial_samples >= interval_samples
                    and samples >= self.settings.sample_rate * 2
                ):
                    last_partial_samples = samples
                    self.on_partial(np.concatenate(utterance))

                if event == "utterance_end" and utterance:
                    audio = np.concatenate(utterance)
                    self.on_utterance(CapturedUtterance(audio, last_speech_time))
                    utterance = []
                    pre_roll.clear()
                    last_partial_samples = 0
        except Exception as exc:
            self.on_error(exc)

    def _drain_frames(self) -> None:
        while True:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                return
