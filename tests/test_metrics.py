import json

from nero.metrics import MetricsCollector, TurnMetrics


def test_metrics_log_has_no_conversation_content(tmp_path) -> None:
    collector = MetricsCollector(tmp_path / "metrics.jsonl")
    turn = TurnMetrics(1, 10.0)
    turn.mark("stt_final", 10.1)
    turn.mark("llm_first_token", 10.3)
    turn.mark("tts_first_pcm", 10.5)
    turn.mark("audio_play_start", 10.6)
    turn.mark("response_end", 10.8)
    result = collector.save(turn)

    assert result["speech_to_audio_ms"] == 600.0
    record = json.loads((tmp_path / "metrics.jsonl").read_text())
    assert "transcript" not in record
    assert "response" not in record
