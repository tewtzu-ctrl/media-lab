"""The `short` recipe: reframe to a vertical export and gate its quality.

Pipeline: resize -> verify the actual aspect ratio -> quality gate -> thumbnail.
Nothing here calls a subprocess directly; every kino invocation goes through
`KinoRunner`, and every render is confirmed with `verify.verify_render`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import paths
from ..config import Config
from ..errors import MediaLabError, VerificationError
from ..kino import KinoRunner
from ..probe import MediaInfo
from ..verify import ASPECT_RATIOS, Expectations, verify_render

VALID_QUALITIES: frozenset[str] = frozenset({"low", "medium", "high", "ultra"})
THUMBNAIL_SUFFIX = ".jpg"


@dataclass(frozen=True, slots=True)
class QualityCheck:
    """One dimension of the `kino video-quality-check` report."""

    name: str
    passed: bool
    score: float
    message: str


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Shape-validated result of `kino video-quality-check`."""

    overall_score: float
    all_passed: bool
    checks: tuple[QualityCheck, ...]
    recommendations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ShortResult:
    """Outcome of exporting a vertical short."""

    info: MediaInfo
    thumbnail_path: Path | None
    quality_report: QualityReport


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise MediaLabError(f"quality-check report field {field!r} is not a string: {value!r}")
    return value


def _require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise MediaLabError(f"quality-check report field {field!r} is not a boolean: {value!r}")
    return value


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MediaLabError(f"quality-check report field {field!r} is not a number: {value!r}")
    return float(value)


def _parse_check(raw: Any) -> QualityCheck:
    if not isinstance(raw, dict):
        raise MediaLabError(f"quality-check entry is not an object: {raw!r}")
    return QualityCheck(
        name=_require_str(raw.get("name"), "checks[].name"),
        passed=_require_bool(raw.get("passed"), "checks[].passed"),
        score=_require_number(raw.get("score"), "checks[].score"),
        message=_require_str(raw.get("message"), "checks[].message"),
    )


def _parse_quality_report(payload: dict[str, Any]) -> QualityReport:
    """Validate the shape of the quality-check JSON before trusting any field."""
    raw_checks = payload.get("checks")
    if not isinstance(raw_checks, list):
        raise MediaLabError(f"quality-check report is missing a 'checks' list: {payload!r}")

    raw_recommendations = payload.get("recommendations", [])
    if not isinstance(raw_recommendations, list):
        raise MediaLabError(
            f"quality-check report field 'recommendations' is not a list: {raw_recommendations!r}"
        )

    return QualityReport(
        overall_score=_require_number(payload.get("overall_score"), "overall_score"),
        all_passed=_require_bool(payload.get("all_passed"), "all_passed"),
        checks=tuple(_parse_check(item) for item in raw_checks),
        recommendations=tuple(
            _require_str(item, "recommendations[]") for item in raw_recommendations
        ),
    )


def _validate_options(aspect_ratio: str, quality: str) -> None:
    """Reject values kinocut's `resize` command does not accept, before any I/O."""
    if aspect_ratio not in ASPECT_RATIOS:
        raise MediaLabError(
            f"unsupported aspect ratio {aspect_ratio!r}, expected one of {sorted(ASPECT_RATIOS)}"
        )
    if quality not in VALID_QUALITIES:
        raise MediaLabError(
            f"unsupported quality {quality!r}, expected one of {sorted(VALID_QUALITIES)}"
        )


def to_short(
    source: Path,
    output: Path,
    config: Config,
    runner: KinoRunner,
    *,
    aspect_ratio: str = "9:16",
    quality: str = "high",
    thumbnail: bool = True,
    fail_on_warning: bool = False,
    force: bool = False,
) -> ShortResult:
    """Reframe `source` to a vertical short and gate its quality before returning.

    Runs `kino resize`, verifies the rendered aspect ratio actually matches
    (a silently wrong reframe is a bug, not a warning), runs
    `kino video-quality-check` and parses its report, and optionally renders a
    thumbnail next to the output.

    Args:
        source: Path to the input clip.
        output: Path for the rendered short. Refused if it already exists,
            unless `force` is set.
        config: Resolved project configuration.
        runner: The single channel through which `kino` is invoked.
        aspect_ratio: One of kinocut's resize presets (default "9:16").
        quality: One of kinocut's resize quality presets (default "high").
        thumbnail: Whether to also render a JPEG thumbnail of the output.
        fail_on_warning: Raise if the quality gate does not fully pass.
        force: Allow overwriting an existing output (and thumbnail).

    Returns:
        A ShortResult carrying the verified MediaInfo, the thumbnail path (if
        one was made), and the parsed quality report.

    Raises:
        MediaLabError: `aspect_ratio` or `quality` is not a value kinocut
            accepts, or the quality-check JSON did not have the expected shape.
        PathSafetyError: `source` is unusable, or `output` cannot be written.
        KinoError: A `kino` invocation failed.
        KinoTimeoutError: A `kino` invocation exceeded its timeout.
        VerificationError: The render did not match `aspect_ratio`, or
            `fail_on_warning` is set and the quality gate did not pass.
    """
    _validate_options(aspect_ratio, quality)

    resolved_source = paths.ensure_readable_source(source)
    resolved_output = paths.ensure_writable_output(output, config, force=force)

    runner.run_json(
        [
            "resize",
            str(resolved_source),
            "-a",
            aspect_ratio,
            "-q",
            quality,
            "-o",
            str(resolved_output),
        ]
    )
    info = verify_render(resolved_output, config, Expectations(aspect_ratio=aspect_ratio))

    quality_payload = runner.run_json(["video-quality-check", str(resolved_output)])
    report = _parse_quality_report(quality_payload)
    if fail_on_warning and not report.all_passed:
        problems = tuple(
            f"{check.name}: {check.message}" for check in report.checks if not check.passed
        )
        raise VerificationError(str(resolved_output), problems)

    thumbnail_path: Path | None = None
    if thumbnail:
        thumbnail_path = paths.ensure_writable_output(
            resolved_output.with_suffix(THUMBNAIL_SUFFIX), config, force=force
        )
        runner.run(["thumbnail", str(resolved_output), "-o", str(thumbnail_path)])

    return ShortResult(info=info, thumbnail_path=thumbnail_path, quality_report=report)
