from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import threading
from typing import Any


@dataclass
class TurnMetrics:
    turn_id: int
    speech_end: float
    marks: dict[str, float] = field(default_factory=dict)
    lm_stats: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None

    def mark(self, name: str, value: float) -> None:
        self.marks.setdefault(name, value)

    def record(self) -> dict[str, Any]:
        def elapsed(start: float | None, end: float | None) -> float | None:
            if start is None or end is None:
                return None
            return round((end - start) * 1000, 2)

        audio_start = self.marks.get("audio_play_start")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "turn_id": self.turn_id,
            "speech_to_stt_ms": elapsed(self.speech_end, self.marks.get("stt_final")),
            "stt_to_first_token_ms": elapsed(
                self.marks.get("stt_final"), self.marks.get("llm_first_token")
            ),
            "first_token_to_pcm_ms": elapsed(
                self.marks.get("llm_first_token"), self.marks.get("tts_first_pcm")
            ),
            "pcm_to_audio_ms": elapsed(
                self.marks.get("tts_first_pcm"), audio_start
            ),
            "speech_to_audio_ms": elapsed(self.speech_end, audio_start),
            "response_total_ms": elapsed(
                self.speech_end, self.marks.get("response_end")
            ),
            "lm_tokens_per_second": self.lm_stats.get("tokens_per_second"),
            "lm_reported_ttft_ms": (
                round(float(self.lm_stats["time_to_first_token_seconds"]) * 1000, 2)
                if self.lm_stats.get("time_to_first_token_seconds") is not None
                else None
            ),
            "input_tokens": self.lm_stats.get("input_tokens"),
            "output_tokens": self.lm_stats.get("total_output_tokens"),
            "error_type": self.error_type,
        }


class MetricsCollector:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self._latencies: list[float] = []
        self._lock = threading.Lock()

    def save(self, metrics: TurnMetrics) -> dict[str, Any]:
        record = metrics.record()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            latency = record.get("speech_to_audio_ms")
            if latency is not None and metrics.error_type is None:
                self._latencies.append(float(latency))
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            summary = self.summary()
        return {**record, **summary}

    def summary(self) -> dict[str, float | int | None]:
        values = sorted(self._latencies)
        if not values:
            return {"turns": 0, "p50_ms": None, "p95_ms": None}
        return {
            "turns": len(values),
            "p50_ms": round(statistics.median(values), 2),
            "p95_ms": round(_percentile(values, 0.95), 2),
        }


def _percentile(values: list[float], quantile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction
