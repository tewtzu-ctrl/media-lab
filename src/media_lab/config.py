"""Configuration, read from the environment and validated at startup.

The project must fail loudly here rather than three stages into a render.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

DEFAULT_FFMPEG_DIR = "./bin"
DEFAULT_IN_DIR = "./in"
DEFAULT_OUT_DIR = "./out"
DEFAULT_WORK_DIR = "./work"
DEFAULT_KINO_TIMEOUT_S = 1800
MIN_KINO_TIMEOUT_S = 1
REQUIRED_BINARIES = ("ffmpeg", "ffprobe")


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved, validated settings. Immutable once built."""

    root: Path
    ffmpeg_dir: Path
    in_dir: Path
    out_dir: Path
    work_dir: Path
    kino_timeout_s: int
    hyperframes_command: Path | None

    @property
    def ffmpeg(self) -> Path:
        return self.ffmpeg_dir / "ffmpeg"

    @property
    def ffprobe(self) -> Path:
        return self.ffmpeg_dir / "ffprobe"


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE .env file. Missing file yields an empty mapping."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _resolve_dir(root: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _parse_timeout(raw: str) -> int:
    try:
        timeout = int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"MEDIA_LAB_KINO_TIMEOUT_S must be a whole number of seconds, got {raw!r}"
        ) from exc
    if timeout < MIN_KINO_TIMEOUT_S:
        raise ConfigError(
            f"MEDIA_LAB_KINO_TIMEOUT_S must be at least {MIN_KINO_TIMEOUT_S}, got {timeout}"
        )
    return timeout


def _check_binaries(ffmpeg_dir: Path) -> None:
    missing = [
        name
        for name in REQUIRED_BINARIES
        if not (ffmpeg_dir / name).is_file() or not os.access(ffmpeg_dir / name, os.X_OK)
    ]
    if missing:
        raise ConfigError(
            f"missing or non-executable in {ffmpeg_dir}: {', '.join(missing)}. "
            "Run ./scripts/fetch-ffmpeg.sh to install them."
        )


def _check_directories_are_distinct(in_dir: Path, out_dir: Path, work_dir: Path) -> None:
    """Overlapping directories only fail much later, on the first write."""
    named = (
        ("MEDIA_LAB_IN_DIR", in_dir),
        ("MEDIA_LAB_OUT_DIR", out_dir),
        ("MEDIA_LAB_WORK_DIR", work_dir),
    )
    for first_name, first in named:
        for second_name, second in named:
            if first_name >= second_name:
                continue
            if first == second:
                raise ConfigError(f"{first_name} and {second_name} point at the same path: {first}")
            if first in second.parents or second in first.parents:
                raise ConfigError(
                    f"{first_name} ({first}) and {second_name} ({second}) are nested; "
                    "they must be separate directories"
                )


def load_config(
    root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Config:
    """Build a validated Config. Raises ConfigError on anything unusable."""
    project_root = (root or Path.cwd()).resolve()
    merged: dict[str, str] = {}
    merged.update(read_env_file(project_root / ".env"))
    merged.update(os.environ if env is None else env)

    ffmpeg_dir = _resolve_dir(project_root, merged.get("MEDIA_LAB_FFMPEG_DIR", DEFAULT_FFMPEG_DIR))
    _check_binaries(ffmpeg_dir)

    in_dir = _resolve_dir(project_root, merged.get("MEDIA_LAB_IN_DIR", DEFAULT_IN_DIR))
    if not in_dir.is_dir():
        raise ConfigError(f"source directory does not exist: {in_dir}")

    out_dir = _resolve_dir(project_root, merged.get("MEDIA_LAB_OUT_DIR", DEFAULT_OUT_DIR))
    work_dir = _resolve_dir(project_root, merged.get("MEDIA_LAB_WORK_DIR", DEFAULT_WORK_DIR))
    _check_directories_are_distinct(in_dir, out_dir, work_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    raw_hyperframes = merged.get("MCP_VIDEO_HYPERFRAMES_COMMAND", "").strip()
    hyperframes = Path(raw_hyperframes) if raw_hyperframes else None
    if hyperframes is not None and not hyperframes.is_absolute():
        hyperframes = (project_root / hyperframes).resolve()

    return Config(
        root=project_root,
        ffmpeg_dir=ffmpeg_dir,
        in_dir=in_dir,
        out_dir=out_dir,
        work_dir=work_dir,
        kino_timeout_s=_parse_timeout(
            merged.get("MEDIA_LAB_KINO_TIMEOUT_S", str(DEFAULT_KINO_TIMEOUT_S))
        ),
        hyperframes_command=hyperframes,
    )
