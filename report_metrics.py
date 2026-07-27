from __future__ import annotations

import json
from pathlib import Path
import statistics

from nero.config import load_settings


def percentile(values: list[float], quantile: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def main() -> None:
    root = Path(__file__).resolve().parent
    settings = load_settings(root / "settings.toml")
    if not settings.log_path.exists():
        raise SystemExit("Ainda não há métricas.")
    records = [
        json.loads(line)
        for line in settings.log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    valid = [
        row
        for row in records
        if row.get("error_type") is None
        and row.get("speech_to_audio_ms") is not None
    ]
    if not valid:
        raise SystemExit("Ainda não há turnos completos.")

    latencies = [float(row["speech_to_audio_ms"]) for row in valid]
    p50 = statistics.median(latencies)
    p95 = percentile(latencies, 0.95)
    print(f"Turnos válidos: {len(valid)}")
    print(f"P50: {p50:.0f} ms / meta {settings.target_p50_ms} ms")
    print(f"P95: {p95:.0f} ms / meta {settings.target_p95_ms} ms")
    print("\nEtapas (p50 / p95):")
    for field, label in (
        ("speech_to_stt_ms", "fim da fala -> STT"),
        ("stt_to_first_token_ms", "STT -> primeiro token"),
        ("first_token_to_pcm_ms", "primeiro token -> PCM"),
        ("pcm_to_audio_ms", "PCM -> reprodução"),
    ):
        values = [
            float(row[field])
            for row in valid
            if isinstance(row.get(field), (int, float))
        ]
        if values:
            print(
                f"- {label}: {statistics.median(values):.0f} / "
                f"{percentile(values, 0.95):.0f} ms"
            )
    print(
        "Resultado: "
        + (
            "META ATINGIDA"
            if len(valid) >= 30
            and p50 <= settings.target_p50_ms
            and p95 <= settings.target_p95_ms
            else "META AINDA NÃO COMPROVADA"
        )
    )


if __name__ == "__main__":
    main()
