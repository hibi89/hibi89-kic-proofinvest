"""Test-only subprocess capture that is stable on Windows and UTF-8 explicit.

Avoids dependence on a process-global subprocess.run wrapper and guarantees
both child output streams are captured before assertions inspect them.
"""
from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence


def run_captured(
    args: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = list(args)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    with subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
        if stdout is None or stderr is None:
            raise RuntimeError("CHILD_OUTPUT_CAPTURE_UNAVAILABLE")
        result = subprocess.CompletedProcess(
            command, process.returncode, stdout, stderr
        )
    if check and result.returncode:
        raise subprocess.CalledProcessError(
            result.returncode, command, output=result.stdout, stderr=result.stderr
        )
    return result
