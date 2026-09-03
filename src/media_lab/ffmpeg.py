"""The single place that invokes ffmpeg directly.

Most work goes through kinocut. A few operations do not: kinocut 1.15.1's
`audio-bed` cannot run on macOS (it requires Linux-only memfd sealing), so
the music bed is built here instead.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .errors import FFmpegError

DEFAULT_FFMPEG_TIMEOUT_S = 900
LOUDNESS_STATS_PATTERN = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.DOTALL)
SILENT_LUFS = -70.0
ALPHA_STAT_PATTERN = re.compile(r"lavfi\.signalstats\.Y(MIN|MAX)=(\d+)")
# ffmpeg's native vp9 decoder does not expose the alpha plane; libvpx-vp9 does.
VP9_ALPHA_DECODER = "libvpx-vp9"


@dataclass(frozen=True, slots=True)
class FFmpegResult:
    """Outcome of one successful ffmpeg invocation."""

    args: tuple[str, ...]
    stderr: str


def run_ffmpeg(
    args: list[str], config: Config, *, timeout_s: int = DEFAULT_FFMPEG_TIMEOUT_S
) -> FFmpegResult:
    """Invoke the project's ffmpeg. Raises FFmpegError on any failure."""
    command = [str(config.ffmpeg), "-hide_banner", "-nostdin", "-y", *args]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed executable, no shell
            command, capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(tuple(args), -1, f"timed out after {timeout_s}s") from exc

    if completed.returncode != 0:
        raise FFmpegError(tuple(args), completed.returncode, completed.stderr)
    return FFmpegResult(args=tuple(args), stderr=completed.stderr)


def measure_integrated_loudness(path: Path, config: Config) -> float:
    """Measure a file's integrated loudness in LUFS with an analysis pass."""
    result = run_ffmpeg(
        ["-i", str(path), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        config,
        timeout_s=DEFAULT_FFMPEG_TIMEOUT_S,
    )
    match = LOUDNESS_STATS_PATTERN.search(result.stderr)
    if match is None:
        raise FFmpegError(("loudnorm",), 0, f"no loudness statistics reported for {path}")

    import json

    try:
        stats = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise FFmpegError(("loudnorm",), 0, f"unparseable loudness statistics: {exc}") from exc

    raw = stats.get("input_i")
    try:
        measured = float(raw)
    except (TypeError, ValueError) as exc:
        raise FFmpegError(("loudnorm",), 0, f"loudness statistics had no input_i: {raw!r}") from exc
    # ffmpeg reports -inf for pure silence; clamp so callers get a usable number.
    return SILENT_LUFS if measured < SILENT_LUFS else measured


def measure_alpha_spread(path: Path, config: Config) -> int:
    """Return how far the alpha channel varies across one frame, on a 0-255 scale.

    A cutout whose alpha never varies carries no matte at all: the subject was
    never separated from its background. That still renders and probes as a
    valid file, so it has to be measured rather than assumed.
    """
    args = ["-hide_banner"]
    if path.suffix.lower() == ".webm":
        args += ["-c:v", VP9_ALPHA_DECODER]
    args += [
        "-i",
        str(path),
        # Normalising to 8-bit first keeps the statistics on one scale whatever
        # bit depth the source carries.
        "-vf",
        "format=yuva444p,alphaextract,signalstats,metadata=print",
        "-frames:v",
        "1",
        "-f",
        "null",
        "-",
    ]
    stderr = run_ffmpeg(args, config, timeout_s=DEFAULT_FFMPEG_TIMEOUT_S).stderr

    found = dict(ALPHA_STAT_PATTERN.findall(stderr))
    if "MIN" not in found or "MAX" not in found:
        raise FFmpegError(("alphaextract",), 0, f"no alpha statistics reported for {path}")
    return int(found["MAX"]) - int(found["MIN"])
