"""Cut a person out of a still or a video, keeping the alpha channel.

Wraps `kino hyperframes-remove-background`, which uses the u2net_human_seg
model through Hyperframes. Object and product cutouts need the
`kinocut[object-matte]` extra, which this project does not install.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Config
from ..errors import MediaLabError, ValidationError, VerificationError
from ..ffmpeg import measure_alpha_spread
from ..kino import KinoRunner
from ..paths import ensure_readable_source, ensure_writable_output
from ..probe import MediaInfo
from ..verify import Expectations, verify_render

PEOPLE_MODEL = "u2net_human_seg"
OBJECT_MODEL = "birefnet-general"
QUALITY_CHOICES = ("fast", "balanced", "best")
DEVICE_CHOICES = ("auto", "cpu", "coreml", "cuda")
# ProRes 4444 in .mov carries alpha that ffmpeg reads natively. VP9-in-WebM
# also carries alpha, but only the libvpx-vp9 decoder exposes it, and
# kinocut's compositor does not request that decoder - it would silently
# composite the subject as an opaque rectangle.
VIDEO_SUFFIX = ".mov"
IMAGE_SUFFIX = ".png"
IMAGE_INPUT_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")
# A matte that never varies means nothing was separated from the background.
MIN_ALPHA_SPREAD = 1


@dataclass(frozen=True, slots=True)
class CutoutResult:
    """A finished cutout, plus what the model reported while producing it."""

    media: MediaInfo
    model: str
    provider: str
    frames_processed: int
    ms_per_frame: float
    alpha_spread: int

    @property
    def is_still(self) -> bool:
        return self.frames_processed <= 1


def _validate_choice(value: str, allowed: tuple[str, ...], label: str) -> str:
    if value not in allowed:
        raise ValidationError(f"{label} must be one of {', '.join(allowed)}, got {value!r}")
    return value


def _expected_suffix(source: Path) -> str:
    return IMAGE_SUFFIX if source.suffix.lower() in IMAGE_INPUT_SUFFIXES else VIDEO_SUFFIX


def _validate_output_suffix(source: Path, output: Path) -> None:
    wanted = _expected_suffix(source)
    if output.suffix.lower() != wanted:
        raise ValidationError(
            f"cutout of {source.suffix} input must be written as {wanted}, got {output.suffix!r}"
        )


def _read_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """kino nests the Hyperframes report under `data`; never trust it blindly."""
    data = payload.get("data")
    if not isinstance(data, dict):
        raise MediaLabError(f"remove-background returned no usable data block: {payload!r}")
    if data.get("ok") is False:
        raise MediaLabError(f"remove-background reported failure: {data!r}")
    return data


def _as_float(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _as_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, int):
        return value
    return 0


def cut_out_person(
    source: Path | str,
    output: Path | str,
    config: Config,
    runner: KinoRunner,
    *,
    quality: str = "balanced",
    device: str = "auto",
    force: bool = False,
) -> CutoutResult:
    """Remove the background behind a person, leaving a transparent cutout."""
    resolved_source = ensure_readable_source(source)
    resolved_output = ensure_writable_output(output, config, force=force)
    _validate_output_suffix(resolved_source, resolved_output)
    _validate_choice(quality, QUALITY_CHOICES, "quality")
    _validate_choice(device, DEVICE_CHOICES, "device")

    payload = runner.run_json(
        [
            "hyperframes-remove-background",
            str(resolved_source),
            "-o",
            str(resolved_output),
            "--model",
            PEOPLE_MODEL,
            "--quality",
            quality,
            "--device",
            device,
        ]
    )
    data = _read_payload(payload)

    media = verify_render(
        resolved_output,
        config,
        Expectations(requires_alpha=True, requires_audio=False),
    )
    alpha_spread = measure_alpha_spread(resolved_output, config)
    if alpha_spread < MIN_ALPHA_SPREAD:
        raise VerificationError(
            str(resolved_output),
            ("alpha channel is uniform: nothing was separated from the background",),
        )
    return CutoutResult(
        media=media,
        model=str(data.get("model", PEOPLE_MODEL)),
        provider=str(data.get("provider", "unknown")),
        frames_processed=_as_int(data, "framesProcessed"),
        ms_per_frame=_as_float(data, "avgMsPerFrame"),
        alpha_spread=alpha_spread,
    )
