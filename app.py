from pathlib import Path
import subprocess

from nero.config import load_settings
from nero.gui import NeroWindow


def stop_lmstudio(base_dir: Path) -> None:
    script = base_dir / "stop_lmstudio.ps1"
    if not script.exists():
        return
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        check=False,
    )


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    try:
        settings = load_settings(base_dir / "settings.toml")
        NeroWindow(settings).run()
    finally:
        stop_lmstudio(base_dir)


if __name__ == "__main__":
    main()
