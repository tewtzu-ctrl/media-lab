"""Place a cutout subject on a new backdrop.

Wraps `kino composite-layers`, which takes a JSON spec and renders a
video-only result: any audio has to be re-attached downstream.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Config
from ..errors import MediaLabError, ValidationError
from ..kino import KinoRunner
from ..paths import ensure_readable_source, ensure_writable_output, work_path
from ..probe import MediaInfo, probe
from ..verify import Expectations, verify_render

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
BACKDROP_LAYER_ID = "backdrop"
SUBJECT_LAYER_ID = "subject"
DEFAULT_BACKGROUND = "#000000"
MIN_SCALE = 0.01
MAX_SCALE = 10.0
MIN_OPACITY = 0.0
MAX_OPACITY = 1.0
STILL_FPS_FALLBACK = 25.0
# kinocut 1.15.1's compositor always renders at most 25 fps but tags the
# output with whatever the canvas asked for, so a 30 fps canvas silently
# loses 25/30 of its running time. Clamping keeps the duration honest.
COMPOSITOR_MAX_FPS = 25.0


@dataclass(frozen=True, slots=True)
class BackdropResult:
    """The composited render, plus the spec that produced it."""

    media: MediaInfo
    spec_path: Path
    canvas_width: int
    canvas_height: int
    canvas_fps: float
    source_fps: float
    backdrop_was_shorter: bool

    @property
    def fps_was_clamped(self) -> bool:
        return self.source_fps > self.canvas_fps


def _stage_beside_spec(source: Path, spec_dir: Path, layer_id: str) -> str:
    """Place a source under the spec directory and return its relative name.

    kinocut confines every layer source to the spec directory, so a clip in
    in/ or out/ cannot be referenced directly. A hard link costs no disk space
    on the same filesystem; a copy is the fallback across filesystems.
    """
    spec_dir.mkdir(parents=True, exist_ok=True)
    staged = spec_dir / f"{layer_id}{source.suffix}"
    if staged.exists():
        staged.unlink()
    try:
        os.link(source, staged)
    except OSError:
        shutil.copy2(source, staged)
    return staged.name


def _layer_type(path: Path) -> str:
    return "image" if path.suffix.lower() in IMAGE_SUFFIXES else "video"


def _check_range(value: float, low: float, high: float, label: str) -> float:
    if not low <= value <= high:
        raise ValidationError(f"{label} must be between {low} and {high}, got {value}")
    return value


def _canvas_size(backdrop: MediaInfo, width: int | None, height: int | None) -> tuple[int, int]:
    resolved_width = width if width is not None else backdrop.width
    resolved_height = height if height is not None else backdrop.height
    if resolved_width <= 0 or resolved_height <= 0:
        raise MediaLabError(
            f"could not determine a canvas size from {backdrop.path} "
            f"({backdrop.width}x{backdrop.height}); pass width and height explicitly"
        )
    return resolved_width, resolved_height


def _build_spec(
    backdrop: str,
    subject: str,
    backdrop_type: str,
    canvas_width: int,
    canvas_height: int,
    fps: float,
    duration: float,
    position: tuple[float, float],
    scale: float,
    opacity: float,
    background: str,
) -> dict[str, Any]:
    subject_layer: dict[str, Any] = {
        "id": SUBJECT_LAYER_ID,
        "type": "video",
        "src": subject,
        "position": {"x": position[0], "y": position[1]},
        "opacity": opacity,
    }
    if scale != 1.0:
        subject_layer["scale"] = scale

    return {
        "canvas": {
            "width": canvas_width,
            "height": canvas_height,
            "fps": fps,
            "duration": duration,
            "background": background,
        },
        "layers": [
            {
                "id": BACKDROP_LAYER_ID,
                "type": backdrop_type,
                "src": backdrop,
                "position": {"x": 0, "y": 0},
                "width": canvas_width,
                "height": canvas_height,
            },
            subject_layer,
        ],
    }


def place_on_backdrop(
    subject: Path | str,
    backdrop: Path | str,
    output: Path | str,
    config: Config,
    runner: KinoRunner,
    *,
    width: int | None = None,
    height: int | None = None,
    position: tuple[float, float] = (0.0, 0.0),
    scale: float = 1.0,
    opacity: float = 1.0,
    background: str = DEFAULT_BACKGROUND,
    force: bool = False,
) -> BackdropResult:
    """Composite a cutout over a backdrop image or video."""
    resolved_subject = ensure_readable_source(subject)
    resolved_backdrop = ensure_readable_source(backdrop)
    resolved_output = ensure_writable_output(output, config, force=force)
    _check_range(scale, MIN_SCALE, MAX_SCALE, "scale")
    _check_range(opacity, MIN_OPACITY, MAX_OPACITY, "opacity")

    subject_info = probe(resolved_subject, config)
    backdrop_info = probe(resolved_backdrop, config)
    if not subject_info.has_video:
        raise MediaLabError(f"subject has no video stream: {resolved_subject}")

    canvas_width, canvas_height = _canvas_size(backdrop_info, width, height)
    source_fps = subject_info.fps if subject_info.fps > 0 else STILL_FPS_FALLBACK
    fps = min(source_fps, COMPOSITOR_MAX_FPS)
    duration = subject_info.duration_s
    if duration <= 0:
        raise MediaLabError(f"subject has no measurable duration: {resolved_subject}")

    is_still_backdrop = _layer_type(resolved_backdrop) == "image"
    backdrop_was_shorter = not is_still_backdrop and 0 < backdrop_info.duration_s < duration

    spec_dir = work_path(config, resolved_output.stem, ".d")
    staged_backdrop = _stage_beside_spec(resolved_backdrop, spec_dir, BACKDROP_LAYER_ID)
    staged_subject = _stage_beside_spec(resolved_subject, spec_dir, SUBJECT_LAYER_ID)

    spec = _build_spec(
        staged_backdrop,
        staged_subject,
        _layer_type(resolved_backdrop),
        canvas_width,
        canvas_height,
        fps,
        duration,
        position,
        scale,
        opacity,
        background,
    )
    spec_path = spec_dir / "layers.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    runner.run_json(["composite-layers", "--spec", str(spec_path), "-o", str(resolved_output)])

    media = verify_render(
        resolved_output,
        config,
        Expectations(
            duration_s=duration,
            width=canvas_width,
            height=canvas_height,
            requires_audio=False,
        ),
    )
    return BackdropResult(
        media=media,
        spec_path=spec_path,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        canvas_fps=fps,
        source_fps=source_fps,
        backdrop_was_shorter=backdrop_was_shorter,
    )
