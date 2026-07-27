from __future__ import annotations

import asyncio
from dataclasses import dataclass
import queue
import threading
import time
from typing import Any

import numpy as np

from nero.audio import CapturedUtterance, MicrophoneEngine
from nero.chunker import SpeechChunker
from nero.config import AppSettings
from nero.lmstudio import LMStudioClient
from nero.metrics import MetricsCollector, TurnMetrics
from nero.stt import LowAudioSignalError, SpeechRecognizer
from nero.tts import SpeechSynthesizer


@dataclass(frozen=True)
class UIEvent:
    kind: str
    value: Any = None


class NeroController:
    def __init__(
        self, settings: AppSettings, ui_events: queue.Queue[UIEvent]
    ) -> None:
        self.settings = settings
        self.ui_events = ui_events
        self.metrics = MetricsCollector(settings.log_path)
        self.llm = LMStudioClient(settings.llm)
        self.stt = SpeechRecognizer(settings.stt)
        self.tts = SpeechSynthesizer(settings.tts, settings.audio)
        self.mic: MicrophoneEngine | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._shutdown: asyncio.Event | None = None
        self._active_task: asyncio.Task[None] | None = None
        self._active_cancel = threading.Event()
        self._paused = False
        self._turn_id = 0
        self._generation = 0
        self._fallback_attempted = False
        self._lm_ttfts: list[float] = []

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._thread_main, name="nero-runtime", daemon=True
        )
        self._thread.start()

    def toggle_pause(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._set_paused, not self._paused)

    def new_conversation(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._new_conversation)

    def stop(self) -> None:
        if self._loop and not self._loop.is_closed() and self._shutdown:
            self._loop.call_soon_threadsafe(self._shutdown.set)
        if self._thread:
            self._thread.join(timeout=5)

    def _emit(self, kind: str, value: Any = None) -> None:
        self.ui_events.put(UIEvent(kind, value))

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._lifecycle())
        except Exception as exc:
            self._emit("error", str(exc))
            self._emit("state", "Erro")

    async def _lifecycle(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._shutdown = asyncio.Event()
        self._emit("state", "Inicializando")
        self._emit("detail", "Carregando voz e reconhecimento local…")

        await asyncio.to_thread(self.stt.start)
        await asyncio.to_thread(self.tts.start)
        await self.llm.health()
        self._emit("detail", "Carregando o modelo no LM Studio…")
        await self.llm.load_model()
        await self.llm.warmup()
        await self.tts.warmup()

        self.mic = MicrophoneEngine(
            self.settings.audio,
            on_utterance=self._on_utterance,
            on_partial=self._on_partial,
            on_barge_in=self._on_barge_in,
            on_error=self._on_audio_error,
        )
        self.mic.start(self.settings.stt.partial_interval_ms)
        self._emit("detail", f"Microfone: {self.mic.input_device_name}")
        self._emit("state", "Ouvindo")

        await self._shutdown.wait()
        self._cancel_active()
        if self._active_task:
            await asyncio.gather(self._active_task, return_exceptions=True)
        if self.mic:
            await asyncio.to_thread(self.mic.close)
        await asyncio.to_thread(self.stt.close)
        await asyncio.to_thread(self.tts.close)
        await self.llm.close()

    def _on_utterance(self, utterance: CapturedUtterance) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._begin_turn, utterance)

    def _on_partial(self, audio: np.ndarray) -> None:
        future = self.stt.submit(audio, final=False)
        if future is None:
            return

        def done(completed) -> None:
            try:
                text = completed.result()
                if text:
                    self._emit("transcript_partial", text)
            except Exception:
                pass

        future.add_done_callback(done)

    def _on_barge_in(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._interrupt)

    def _on_audio_error(self, error: Exception) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._fatal, error)

    def _begin_turn(self, utterance: CapturedUtterance) -> None:
        if self._paused:
            return
        self._cancel_active()
        self._turn_id += 1
        self._generation += 1
        generation = self._generation
        self._active_cancel = threading.Event()
        self._active_task = asyncio.create_task(
            self._handle_turn(
                self._turn_id, generation, utterance, self._active_cancel
            )
        )

    def _cancel_active(self) -> None:
        self._active_cancel.set()
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
        if self.mic:
            self.mic.set_playback_active(False)

    def _interrupt(self) -> None:
        self._cancel_active()
        self._emit("state", "Interrompido")
        self._emit("detail", "Te escuto")

    def _set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._cancel_active()
        if self.mic:
            self.mic.set_enabled(not paused)
        self._emit("paused", paused)
        self._emit("state", "Pausado" if paused else "Ouvindo")
        self._emit("detail", "Microfone pausado" if paused else "Pode falar")

    def _new_conversation(self) -> None:
        self._generation += 1
        self._cancel_active()
        self.llm.new_conversation()
        self._emit("clear")
        self._emit("state", "Ouvindo")
        self._emit("detail", "Nova conversa, pode falar")

    def _fatal(self, error: Exception) -> None:
        self._emit("error", str(error))
        self._emit("state", "Erro")

    async def _handle_turn(
        self,
        turn_id: int,
        generation: int,
        utterance: CapturedUtterance,
        cancel: threading.Event,
    ) -> None:
        metrics = TurnMetrics(turn_id, utterance.speech_end)
        self._emit("response_reset")
        self._emit("state", "Pensando")
        self._emit("detail", "Finalizando a transcrição…")
        try:
            future = self.stt.submit(utterance.audio, final=True)
            if future is None:
                raise RuntimeError("Não foi possível agendar a transcrição")
            transcript = await asyncio.wrap_future(future)
            metrics.mark("stt_final", time.perf_counter())
            if not transcript:
                metrics.error_type = "empty_transcript"
                self._emit("detail", "Não entendi. Pode repetir?")
                self._emit("state", "Ouvindo")
                self._emit("metrics", self.metrics.save(metrics))
                return
            self._emit("transcript", transcript)
            self._emit("detail", "Gerando resposta…")

            tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
            tts_task = asyncio.create_task(
                self._tts_worker(tts_queue, metrics, cancel, generation)
            )
            chunker = SpeechChunker()
            first_token = True

            async for event in self.llm.stream_chat(transcript):
                if generation != self._generation or cancel.is_set():
                    raise asyncio.CancelledError
                if event.type == "message.delta" and event.content:
                    if first_token:
                        first_token = False
                        metrics.mark("llm_first_token", time.perf_counter())
                    self._emit("response_delta", event.content)
                    for chunk in chunker.feed(event.content):
                        await tts_queue.put(chunk)
                elif event.type == "chat.end" and event.result:
                    metrics.lm_stats = event.result.get("stats", {})
                    metrics.mark("response_end", time.perf_counter())

            if first_token:
                raise RuntimeError("O LM Studio não produziu texto para este turno.")
            for chunk in chunker.flush():
                await tts_queue.put(chunk)
            await tts_queue.put(None)
            await tts_task
            if generation != self._generation:
                return
            if self.mic:
                self.mic.set_playback_active(False)
            self._emit("state", "Ouvindo")
            self._emit("detail", "Pode falar")
            summary = self.metrics.save(metrics)
            self._emit("metrics", summary)
            ttft = summary.get("lm_reported_ttft_ms")
            if isinstance(ttft, (int, float)):
                self._lm_ttfts.append(float(ttft))
            await self._maybe_switch_fallback(summary)
        except asyncio.CancelledError:
            cancel.set()
            metrics.error_type = "interrupted"
            self.metrics.save(metrics)
            raise
        except LowAudioSignalError as exc:
            cancel.set()
            metrics.error_type = "low_audio_signal"
            self.metrics.save(metrics)
            self._emit("state", "Ouvindo")
            self._emit("detail", str(exc))
        except Exception as exc:
            cancel.set()
            metrics.error_type = type(exc).__name__
            self.metrics.save(metrics)
            self._emit("error", str(exc))
            self._emit("state", "Ouvindo")
            self._emit("detail", "O turno falhou; pode tentar novamente")

    async def _tts_worker(
        self,
        chunks: asyncio.Queue[str | None],
        metrics: TurnMetrics,
        cancel: threading.Event,
        generation: int,
    ) -> None:
        first_pcm = True
        first_audio = True
        while not cancel.is_set():
            chunk = await chunks.get()
            if chunk is None:
                return

            def mark_pcm() -> None:
                nonlocal first_pcm
                if first_pcm:
                    first_pcm = False
                    metrics.mark("tts_first_pcm", time.perf_counter())

            def mark_audio() -> None:
                nonlocal first_audio
                if first_audio:
                    first_audio = False
                    metrics.mark("audio_play_start", time.perf_counter())
                    if self.mic:
                        self.mic.set_playback_active(True)
                    self._emit("state", "Falando")
                    self._emit("detail", "Pode interromper a qualquer momento")

            completed = await self.tts.speak(
                chunk, cancel, mark_pcm, mark_audio
            )
            if not completed or generation != self._generation:
                return

    async def _maybe_switch_fallback(self, summary: dict[str, Any]) -> None:
        if (
            not self.settings.llm.auto_fallback
            or self._fallback_attempted
            or int(summary.get("turns") or 0) < 30
        ):
            return
        p95 = summary.get("p95_ms")
        average_ttft = (
            sum(self._lm_ttfts) / len(self._lm_ttfts) if self._lm_ttfts else 0
        )
        if (
            isinstance(p95, (int, float))
            and p95 > self.settings.target_p95_ms
            and average_ttft > 350
        ):
            self._fallback_attempted = True
            self._emit("detail", "Testando o modelo de reserva por causa do TTFT…")
            try:
                await self.llm.load_model(self.settings.llm.fallback_model)
                await self.llm.warmup()
                self.llm.new_conversation()
                self._emit(
                    "detail",
                    "Modelo de reserva ativado; métricas continuam visíveis",
                )
            except Exception as exc:
                self._emit("error", f"Modelo de reserva indisponível: {exc}")
