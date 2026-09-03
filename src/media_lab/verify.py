"""Verify a render against what was asked for.

Nothing in this project reports success without passing through here first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .errors import VerificationError
from .probe import MediaInfo, probe

DEFAULT_DURATION_TOLERANCE_S = 0.5
MIN_PLAUSIBLE_BYTES = 1024


@dataclass(frozen=True, slots=True)
class Expectations:
    """What a caller believes the render should be. All fields optional."""

    duration_s: float | None = None
    duration_tolerance_s: float = DEFAULT_DURATION_TOLERANCE_S
    width: int | None = None
    height: int | None = None
    aspect_ratio: str | None = None
    requires_video: bool = True
    requires_audio: bool | None = None
    requires_alpha: bool | None = None


ASPECT_RATIOS: dict[str, float] = {
    "16:9": 16 / 9,
    "9:16": 9 / 16,
    "1:1": 1.0,
    "4:3": 4 / 3,
    "4:5": 4 / 5,
    "21:9": 21 / 9,
}
ASPECT_TOLERANCE = 0.02


def _aspect_problem(info: MediaInfo, wanted: str) -> str | None:
    target = ASPECT_RATIOS.get(wanted)
    if target is None:
        return f"unknown aspect ratio {wanted!r}"
    if abs(info.aspect_ratio - target) > ASPECT_TOLERANCE:
        return (
            f"aspect ratio is {info.width}x{info.height} "
            f"({info.aspect_ratio:.3f}), expected {wanted} ({target:.3f})"
        )
    return None


def _collect_problems(info: MediaInfo, expected: Expectations) -> tuple[str, ...]:
    problems: list[str] = []

    if expected.requires_video and not info.has_video:
        problems.append("no video stream")
    if expected.requires_audio is True and not info.has_audio:
        problems.append("no audio stream")
    if expected.requires_audio is False and info.has_audio:
        problems.append("audio stream present but none expected")
    if expected.requires_alpha is True and not info.has_alpha:
        problems.append(f"no alpha channel (pixel format is {info.pixel_format or 'unknown'})")

    if expected.duration_s is not None:
        drift = abs(info.duration_s - expected.duration_s)
        if drift > expected.duration_tolerance_s:
            problems.append(
                f"duration is {info.duration_s:.2f}s, expected "
                f"{expected.duration_s:.2f}s (tolerance {expected.duration_tolerance_s}s)"
            )
    if expected.width is not None and info.width != expected.width:
        problems.append(f"width is {info.width}, expected {expected.width}")
    if expected.height is not None and info.height != expected.height:
        problems.append(f"height is {info.height}, expected {expected.height}")
    if expected.aspect_ratio is not None:
        problem = _aspect_problem(info, expected.aspect_ratio)
        if problem is not None:
            problems.append(problem)

    return tuple(problems)


def verify_render(
    path: Path | str,
    config: Config,
    expected: Expectations | None = None,
) -> MediaInfo:
    """Probe a rendered file and confirm it matches expectations."""
    target = Path(path)
    if not target.is_file():
        raise VerificationError(str(target), ("file was not created",))
    if target.stat().st_size < MIN_PLAUSIBLE_BYTES:
        raise VerificationError(str(target), (f"file is only {target.stat().st_size} bytes",))

    info = probe(target, config)
    problems = _collect_problems(info, expected or Expectations())
    if problems:
        raise VerificationError(str(target), problems)
    return info
