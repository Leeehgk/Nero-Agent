from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

from huggingface_hub import snapshot_download
import httpx


ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"
KOKORO_FILES = {
    "kokoro-v1.0.onnx": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.0/kokoro-v1.0.onnx"
    ),
    "voices-v1.0.bin": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.0/voices-v1.0.bin"
    ),
}


def download_file(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 1_000_000:
        print(f"[OK] {destination.name} já existe")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    print(f"[DOWNLOAD] {destination.name}")
    with httpx.stream(
        "GET", url, follow_redirects=True, timeout=120, trust_env=False
    ) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes(1024 * 1024):
                handle.write(chunk)
    partial.replace(destination)
    print(f"[OK] {destination.name}: {destination.stat().st_size / 1_000_000:.1f} MB")


def download_whisper(repo: str, folder: str) -> None:
    destination = MODELS / folder
    if (destination / "model.bin").exists():
        print(f"[OK] {folder} já existe")
        return
    print(f"[DOWNLOAD] {folder}")
    snapshot_download(
        repo_id=repo,
        local_dir=destination,
    )
    print(f"[OK] {folder}")


def find_lms() -> Path:
    from_path = shutil.which("lms")
    if from_path:
        return Path(from_path)
    candidate = Path.home() / ".lmstudio" / "bin" / "lms.exe"
    if candidate.exists():
        return candidate
    raise RuntimeError("CLI do LM Studio não encontrado")


def download_lm_models() -> None:
    lms = find_lms()
    daemon = subprocess.run(
        [str(lms), "daemon", "up"],
        check=False,
        capture_output=True,
        text=True,
    )
    if daemon.returncode != 0:
        detail = (daemon.stderr or daemon.stdout).strip()
        raise RuntimeError(
            "Não foi possível iniciar o serviço local do LM Studio. "
            "Abra o LM Studio ou instale o llmster e tente novamente. "
            f"Detalhe: {detail}"
        )
    for model in (
        "qwen/qwen3.5-4b@q4_k_m",
        "qwen/qwen3.5-2b@q4_k_m",
    ):
        print(f"[DOWNLOAD] LM Studio: {model}")
        subprocess.run([str(lms), "get", model, "--gguf", "--yes"], check=True)


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    for filename, url in KOKORO_FILES.items():
        download_file(url, MODELS / filename)
    download_whisper("Systran/faster-whisper-base", "faster-whisper-base")
    download_whisper("Systran/faster-whisper-tiny", "faster-whisper-tiny")
    download_lm_models()
    print("\nModelos instalados. O Nero pode funcionar sem internet.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nErro: {exc}", file=sys.stderr)
        raise SystemExit(1)
