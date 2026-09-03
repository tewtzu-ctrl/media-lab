"""The single place that invokes the `kino` CLI.

No other module shells out to kinocut. Everything here is bounded by a
timeout, captures stderr, and raises typed errors.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config
from .errors import KinoError, KinoTimeoutError, MediaLabError

KINO_EXECUTABLE = "kino"


def find_kino() -> Path:
    """Locate the kino executable, preferring the active virtualenv."""
    beside_python = Path(sys.executable).parent / KINO_EXECUTABLE
    if beside_python.is_file():
        return beside_python
    found = shutil.which(KINO_EXECUTABLE)
    if found is None:
        raise MediaLabError("kino executable not found. Run `make setup` to install kinocut.")
    return Path(found)


@dataclass(frozen=True, slots=True)
class KinoResult:
    """Outcome of one successful kino invocation."""

    args: tuple[str, ...]
    stdout: str
    stderr: str
    duration_s: float


@dataclass(frozen=True, slots=True)
class KinoRunner:
    """Runs kino commands with the project's ffmpeg and Hyperframes on PATH."""

    config: Config
    executable: Path

    @classmethod
    def from_config(cls, config: Config) -> KinoRunner:
        return cls(config=config, executable=find_kino())

    def _environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join([str(self.config.ffmpeg_dir), env.get("PATH", "")])
        if self.config.hyperframes_command is not None:
            env["MCP_VIDEO_HYPERFRAMES_COMMAND"] = str(self.config.hyperframes_command)
        return env

    def run(self, args: Sequence[str], *, timeout_s: int | None = None) -> KinoResult:
        """Invoke kino. Raises KinoError or KinoTimeoutError on failure."""
        command = (str(self.executable), *args)
        limit = timeout_s if timeout_s is not None else self.config.kino_timeout_s
        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603 - fixed executable, no shell
                command,
                capture_output=True,
                text=True,
                timeout=limit,
                env=self._environment(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise KinoTimeoutError(tuple(args), limit) from exc

        if completed.returncode != 0:
            raise KinoError(tuple(args), completed.returncode, completed.stderr, completed.stdout)
        return KinoResult(
            args=tuple(args),
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_s=time.monotonic() - started,
        )

    def run_json(self, args: Sequence[str], *, timeout_s: int | None = None) -> dict[str, Any]:
        """Invoke kino in JSON mode and validate the shape of what comes back."""
        result = self.run(["--format", "json", *args], timeout_s=timeout_s)
        payload = _extract_json_object(result.stdout)
        if payload.get("success") is False:
            error = payload.get("error") or payload.get("message") or "unspecified failure"
            raise KinoError(tuple(args), 0, str(error))
        return payload


def _extract_json_object(stdout: str) -> dict[str, Any]:
    """Pull the JSON object out of kino stdout, tolerating leading log noise.

    Log lines can themselves contain braces, so every brace position is a
    candidate: the first one that parses wins.
    """
    candidates = [stdout.strip()]
    candidates += [stdout[index:] for index, char in enumerate(stdout) if char == "{"]

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            raise MediaLabError(f"expected a JSON object from kino, got {type(parsed).__name__}")
        return parsed

    raise MediaLabError(f"could not parse kino JSON output: {stdout[:200]!r}")
