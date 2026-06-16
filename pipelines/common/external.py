from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run_command(template: str, params: dict[str, str], cwd: Path | None = None) -> None:
    command = template.format(**params)
    subprocess.run(command, cwd=cwd, shell=True, check=True, env=os.environ.copy())

