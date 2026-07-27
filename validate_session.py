from __future__ import annotations

import argparse
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


def numbers(value: str) -> list[float]:
    try:
        return [float(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use números separados por vírgula") from exc


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Fecha a validação humana e técnica de uma sessão do Nero."
    )
    result.add_argument(
        "--semantic-correct",
        type=int,
        required=True,
        help="quantas das 30 transcrições mantiveram o sentido",
    )
    result.add_argument(
        "--naturalness",
        type=numbers,
        required=True,
        help="dez notas de 1 a 5, separadas por vírgula",
    )
    result.add_argument(
        "--interruptions-ms",
        type=numbers,
        required=True,
        help="tempos observados para parar o áudio, separados por vírgula",
    )
    return result


def main() -> None:
    args = parser().parse_args()
    if not 0 <= args.semantic_correct <= 30:
        raise SystemExit("--semantic-correct deve estar entre 0 e 30")
    if len(args.naturalness) != 10 or any(
        score < 1 or score > 5 for score in args.naturalness
    ):
        raise SystemExit("--naturalness exige exatamente dez notas entre 1 e 5")
    if not args.interruptions_ms or any(
        value < 0 for value in args.interruptions_ms
    ):
        raise SystemExit("--interruptions-ms exige pelo menos uma medição positiva")

    root = Path(__file__).resolve().parent
    settings = load_settings(root / "settings.toml")
    if not settings.log_path.exists():
        raise SystemExit("Ainda não há métricas em logs/metrics.jsonl")
    rows = [
        json.loads(line)
        for line in settings.log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    valid = [
        row
        for row in rows
        if row.get("error_type") is None
        and isinstance(row.get("speech_to_audio_ms"), (int, float))
    ][-30:]
    if len(valid) < 30:
        raise SystemExit(f"São necessários 30 turnos válidos; encontrei {len(valid)}")

    latencies = [float(row["speech_to_audio_ms"]) for row in valid]
    p50 = statistics.median(latencies)
    p95 = percentile(latencies, 0.95)
    semantic_rate = args.semantic_correct / 30
    naturalness = statistics.mean(args.naturalness)
    interruption_p95 = percentile(args.interruptions_ms, 0.95)
    passed = (
        p50 <= settings.target_p50_ms
        and p95 <= settings.target_p95_ms
        and semantic_rate >= 0.90
        and naturalness >= 4.0
        and interruption_p95 <= 250
    )

    print(f"Latência: p50={p50:.0f} ms, p95={p95:.0f} ms")
    print(f"Semântica: {semantic_rate:.0%}")
    print(f"Naturalidade: {naturalness:.1f}/5")
    print(f"Interrupção: p95={interruption_p95:.0f} ms")
    print("Resultado:", "APROVADO" if passed else "NÃO APROVADO")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
