from __future__ import annotations

from concurrent.futures import Future
from itertools import count
from pathlib import Path
import queue
import threading

import numpy as np
from faster_whisper import WhisperModel

from nero.config import STTSettings


class LowAudioSignalError(RuntimeError):
    """O dispositivo abriu, mas não entregou voz utilizável."""


class SpeechRecognizer:
    """Um único worker com prioridade para a transcrição final."""

    def __init__(self, settings: STTSettings) -> None:
        self.settings = settings
        self._model: WhisperModel | None = None
        self._jobs: queue.PriorityQueue[
            tuple[int, int, np.ndarray | None, Future[str] | None]
        ] = queue.PriorityQueue()
        self._sequence = count()
        self._thread: threading.Thread | None = None
        self._partial_pending = False
        self._partial_lock = threading.Lock()

    def start(self) -> None:
        if not self.settings.model_path.exists():
            raise RuntimeError(
                "Modelo Whisper não encontrado em "
                f"{self.settings.model_path}. Execute: py -3.11 setup_models.py"
            )
        self._model = WhisperModel(
            str(self.settings.model_path),
            device="cpu",
            compute_type="int8",
            cpu_threads=self.settings.cpu_threads,
            num_workers=1,
            local_files_only=True,
        )
        self._thread = threading.Thread(
            target=self._worker, name="nero-stt", daemon=True
        )
        self._thread.start()
        samples = np.arange(8000, dtype=np.float32)
        warmup_audio = 0.01 * np.sin(2 * np.pi * 440 * samples / 16000)
        warmup = self.submit(warmup_audio.astype(np.float32), final=True)
        if warmup is not None:
            warmup.result(timeout=30)

    def submit(self, audio: np.ndarray, final: bool) -> Future[str] | None:
        if not final:
            with self._partial_lock:
                if self._partial_pending:
                    return None
                self._partial_pending = True
        future: Future[str] = Future()
        priority = 0 if final else 10
        self._jobs.put((priority, next(self._sequence), audio.copy(), future))
        return future

    def close(self) -> None:
        self._jobs.put((-1, next(self._sequence), None, None))
        if self._thread:
            self._thread.join(timeout=2)

    def _worker(self) -> None:
        while True:
            priority, _, audio, future = self._jobs.get()
            if audio is None:
                return
            try:
                if self._model is None:
                    raise RuntimeError("Whisper não inicializado")
                centered = audio - float(np.mean(audio))
                rms = float(np.sqrt(np.mean(centered * centered)))
                peak = float(np.max(np.abs(centered)))
                if rms < 0.0005 or peak < 0.003:
                    if priority == 0:
                        raise LowAudioSignalError(
                            "O microfone está sem sinal de voz. No H510-PRO, "
                            "confirme o botão MIC, encaixe o microfone removível "
                            "até o fim e verifique o modo 2,4 GHz/USB."
                        )
                    if future and not future.cancelled():
                        future.set_result("")
                    continue
                beam_size = self.settings.final_beam_size if priority == 0 else 1
                segments, _ = self._model.transcribe(
                    centered,
                    language="pt",
                    beam_size=beam_size,
                    best_of=beam_size,
                    temperature=0,
                    vad_filter=False,
                    word_timestamps=False,
                    condition_on_previous_text=False,
                    without_timestamps=True,
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                if future and not future.cancelled():
                    future.set_result(text)
            except Exception as exc:
                if future and not future.cancelled():
                    future.set_exception(exc)
            finally:
                if priority == 10:
                    with self._partial_lock:
                        self._partial_pending = False
