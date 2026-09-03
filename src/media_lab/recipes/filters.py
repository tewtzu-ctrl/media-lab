"""Recipe: apply a small, curated set of named visual "looks" to a clip.

Each look wraps exactly one `kino` filter or effect command with pre-tuned,
bounds-checked parameters, so callers never pass raw numeric values into
ffmpeg. Two looks can be chained in sequence, with the intermediate render
kept in the work directory for inspection.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal, assert_never

from ..config import Config
from ..errors import ValidationError
from ..kino import KinoRunner
from ..paths import ensure_readable_source, ensure_writable_output, work_path
from ..probe import MediaInfo
from ..verify import verify_render

# Bounds below are confirmed against kinocut's own `validation.py`
# (FILTER_PARAMETER_BOUNDS) and the `--help` output of each effect command.
MIN_FILTER_LEVEL: Final[float] = 0.0
MAX_FILTER_LEVEL: Final[float] = 3.0
MIN_UNIT: Final[float] = 0.0
MAX_UNIT: Final[float] = 1.0
# effect-glow's --radius is documented only as "pixels", with no stated
# range. This ceiling is our own defensive margin, not a kino constraint.
MIN_GLOW_RADIUS_PX: Final[float] = 1.0
MAX_GLOW_RADIUS_PX: Final[float] = 100.0

_FilterLevelType = Literal["saturation", "contrast"]
ColorPreset = Literal["warm", "cool", "vintage", "cinematic", "noir"]
NoiseMode = Literal["film", "digital", "color"]

_FILTER_LEVEL_BOUNDS: Mapping[_FilterLevelType, tuple[float, float]] = MappingProxyType(
    {
        "saturation": (MIN_FILTER_LEVEL, MAX_FILTER_LEVEL),
        "contrast": (MIN_FILTER_LEVEL, MAX_FILTER_LEVEL),
    }
)


@dataclass(frozen=True, slots=True)
class _FilterLook:
    """A look backed by `kino filter -t {saturation,contrast}`."""

    filter_type: _FilterLevelType
    level: float


@dataclass(frozen=True, slots=True)
class _ColorGradeLook:
    """A look backed by `kino color-grade`."""

    preset: ColorPreset


@dataclass(frozen=True, slots=True)
class _VignetteLook:
    """A look backed by `kino effect-vignette`."""

    intensity: float
    radius: float
    smoothness: float


@dataclass(frozen=True, slots=True)
class _GlowLook:
    """A look backed by `kino effect-glow`."""

    intensity: float
    radius: float
    threshold: float


@dataclass(frozen=True, slots=True)
class _GrainLook:
    """A look backed by `kino effect-noise`."""

    intensity: float
    mode: NoiseMode


_LookParams = _FilterLook | _ColorGradeLook | _VignetteLook | _GlowLook | _GrainLook


@dataclass(frozen=True, slots=True)
class LookSpec:
    """A named, pre-tuned visual look backed by exactly one kino command."""

    name: str
    description: str
    params: _LookParams


LOOKS: Mapping[str, LookSpec] = MappingProxyType(
    {
        "warm": LookSpec("warm", "Warm color grade.", _ColorGradeLook(preset="warm")),
        "cool": LookSpec("cool", "Cool color grade.", _ColorGradeLook(preset="cool")),
        "vintage": LookSpec(
            "vintage", "Faded vintage color grade.", _ColorGradeLook(preset="vintage")
        ),
        "cinematic": LookSpec(
            "cinematic",
            "High-contrast cinematic color grade.",
            _ColorGradeLook(preset="cinematic"),
        ),
        "noir": LookSpec(
            "noir", "Desaturated, high-contrast noir color grade.", _ColorGradeLook(preset="noir")
        ),
        "vignette": LookSpec(
            "vignette",
            "Soft dark vignette around the frame edges.",
            _VignetteLook(intensity=0.5, radius=0.8, smoothness=0.5),
        ),
        "glow": LookSpec(
            "glow",
            "Soft bloom on bright highlights.",
            _GlowLook(intensity=0.5, radius=10.0, threshold=0.7),
        ),
        "grain": LookSpec(
            "grain",
            "Subtle animated film grain.",
            _GrainLook(intensity=0.05, mode="film"),
        ),
        "vibrant": LookSpec(
            "vibrant", "Boosted saturation.", _FilterLook(filter_type="saturation", level=1.8)
        ),
        "punchy": LookSpec(
            "punchy", "Boosted contrast.", _FilterLook(filter_type="contrast", level=1.8)
        ),
    }
)


def _ensure_within_bounds(
    value: float, bounds: tuple[float, float], label: str, look_name: str
) -> None:
    """Raise ValidationError if a baked-in look parameter drifted out of range.

    Deliberately not validation.check_range: this guards the catalogue itself
    rather than a caller argument, so the message names the offending look.
    """
    lo, hi = bounds
    if not lo <= value <= hi:
        raise ValidationError(
            f"look {look_name!r} has {label}={value}, outside allowed range [{lo}, {hi}]"
        )


def _validate_look(spec: LookSpec) -> None:
    """Validate every numeric parameter baked into a look against its bounds."""
    match spec.params:
        case _FilterLook(filter_type=filter_type, level=level):
            _ensure_within_bounds(level, _FILTER_LEVEL_BOUNDS[filter_type], "level", spec.name)
        case _ColorGradeLook():
            return
        case _VignetteLook(intensity=intensity, radius=radius, smoothness=smoothness):
            _ensure_within_bounds(intensity, (MIN_UNIT, MAX_UNIT), "intensity", spec.name)
            _ensure_within_bounds(radius, (MIN_UNIT, MAX_UNIT), "radius", spec.name)
            _ensure_within_bounds(smoothness, (MIN_UNIT, MAX_UNIT), "smoothness", spec.name)
        case _GlowLook(intensity=intensity, radius=radius, threshold=threshold):
            _ensure_within_bounds(intensity, (MIN_UNIT, MAX_UNIT), "intensity", spec.name)
            _ensure_within_bounds(
                radius, (MIN_GLOW_RADIUS_PX, MAX_GLOW_RADIUS_PX), "radius", spec.name
            )
            _ensure_within_bounds(threshold, (MIN_UNIT, MAX_UNIT), "threshold", spec.name)
        case _GrainLook(intensity=intensity):
            _ensure_within_bounds(intensity, (MIN_UNIT, MAX_UNIT), "intensity", spec.name)
        case _ as unreachable:
            assert_never(unreachable)


def _resolve_look(look: str) -> LookSpec:
    """Look up a named look, validating it against its parameter bounds."""
    spec = LOOKS.get(look)
    if spec is None:
        valid = ", ".join(sorted(LOOKS))
        raise ValidationError(f"unknown look {look!r}. Valid looks: {valid}")
    _validate_look(spec)
    return spec


def _build_args(params: _LookParams, source: Path, destination: Path) -> tuple[str, ...]:
    """Translate a resolved look into a kino command line."""
    match params:
        case _FilterLook(filter_type=filter_type, level=level):
            payload = json.dumps({"level": level})
            return (
                "filter",
                "-t",
                filter_type,
                "--params",
                payload,
                "-o",
                str(destination),
                str(source),
            )
        case _ColorGradeLook(preset=preset):
            return ("color-grade", "-p", preset, "-o", str(destination), str(source))
        case _VignetteLook(intensity=intensity, radius=radius, smoothness=smoothness):
            return (
                "effect-vignette",
                "-i",
                str(intensity),
                "-r",
                str(radius),
                "-s",
                str(smoothness),
                "-o",
                str(destination),
                str(source),
            )
        case _GlowLook(intensity=intensity, radius=radius, threshold=threshold):
            return (
                "effect-glow",
                "-i",
                str(intensity),
                "-r",
                str(radius),
                "-t",
                str(threshold),
                "-o",
                str(destination),
                str(source),
            )
        case _GrainLook(intensity=intensity, mode=mode):
            return (
                "effect-noise",
                "-i",
                str(intensity),
                "-m",
                mode,
                "-o",
                str(destination),
                str(source),
            )
        case _ as unreachable:
            assert_never(unreachable)


def _render_look(
    spec: LookSpec, source: Path, destination: Path, config: Config, runner: KinoRunner
) -> MediaInfo:
    """Run one kino command for a resolved look and verify the result."""
    args = _build_args(spec.params, source, destination)
    runner.run(args)
    return verify_render(destination, config)


def apply_look(
    source: Path,
    output: Path,
    look: str,
    config: Config,
    runner: KinoRunner,
    *,
    force: bool = False,
) -> MediaInfo:
    """Render one named look onto a clip and verify the result.

    Args:
        source: Input clip. Never modified.
        output: Desired path for the rendered clip.
        look: Name of an entry in `LOOKS`.
        config: Resolved project configuration.
        runner: Shared kino process runner.
        force: Overwrite an existing file at `output` when True.

    Returns:
        Probed information about the verified render.

    Raises:
        ValidationError: `look` is unknown, or one of its parameters drifted
            outside its allowed bounds.
        PathSafetyError: `source` or `output` violate the path contract.
        KinoError: The `kino` invocation failed.
        KinoTimeoutError: The `kino` invocation exceeded its timeout.
        VerificationError: The render does not match what was expected.
    """
    spec = _resolve_look(look)
    resolved_source = ensure_readable_source(source)
    resolved_output = ensure_writable_output(output, config, force=force)
    return _render_look(spec, resolved_source, resolved_output, config, runner)


def apply_look_chain(
    source: Path,
    output: Path,
    first_look: str,
    second_look: str,
    config: Config,
    runner: KinoRunner,
    *,
    force: bool = False,
) -> MediaInfo:
    """Apply two looks in sequence, keeping the intermediate render for inspection.

    `first_look` renders into `config.work_dir`; `second_look` reads that
    intermediate and renders into `output`.

    Raises the same errors as `apply_look`.
    """
    first_spec = _resolve_look(first_look)
    second_spec = _resolve_look(second_look)
    resolved_source = ensure_readable_source(source)
    resolved_output = ensure_writable_output(output, config, force=force)

    intermediate = work_path(
        config, f"{resolved_source.stem}__{first_look}", resolved_source.suffix
    )
    _render_look(first_spec, resolved_source, intermediate, config, runner)
    return _render_look(second_spec, intermediate, resolved_output, config, runner)
