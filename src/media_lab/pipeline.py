"""Run the whole edit in one pass, keeping every intermediate for inspection.

Order: cut the subject out, place it on a backdrop, grade it, restore the
voice the compositor dropped, duck a music bed under it, then export vertical.
Each stage is verified before the next one starts, so a failure names the
stage that produced it and leaves everything already rendered on disk.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .kino import KinoRunner
from .paths import ensure_readable_source, ensure_writable_output, work_path
from .probe import MediaInfo, probe
from .recipes.audio_attach import attach_audio
from .recipes.audio_bed import DEFAULT_TARGET_LUFS, add_music_bed
from .recipes.backdrop import place_on_backdrop
from .recipes.cutout import cut_out_person
from .recipes.filters import apply_look
from .recipes.to_short import QualityReport, to_short

DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_CUTOUT_QUALITY = "balanced"


@dataclass(frozen=True, slots=True)
class Stage:
    """One completed step and the file it produced."""

    name: str
    output: Path


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """The finished clip, plus the trail of intermediates that produced it."""

    final: Path
    media: MediaInfo
    stages: tuple[Stage, ...]
    quality_report: QualityReport
    thumbnail_path: Path | None


def run_pipeline(
    source: Path | str,
    output: Path | str,
    config: Config,
    runner: KinoRunner,
    *,
    backdrop: Path | str | None = None,
    look: str | None = None,
    music: Path | str | None = None,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    cutout_quality: str = DEFAULT_CUTOUT_QUALITY,
    target_lufs: float = DEFAULT_TARGET_LUFS,
    force: bool = False,
) -> PipelineResult:
    """Take one clip from raw footage to a finished vertical social post."""
    resolved_source = ensure_readable_source(source)
    resolved_output = ensure_writable_output(output, config, force=force)
    stem = resolved_output.stem

    source_info = probe(resolved_source, config)
    current = resolved_source
    stages: list[Stage] = []
    audio_dropped = False

    if backdrop is not None:
        cutout = work_path(config, f"{stem}-1-cutout", ".mov")
        cut_out_person(current, cutout, config, runner, quality=cutout_quality, force=True)
        stages.append(Stage("cutout", cutout))

        composed = work_path(config, f"{stem}-2-backdrop", ".mp4")
        place_on_backdrop(cutout, backdrop, composed, config, runner, force=True)
        stages.append(Stage("backdrop", composed))
        current = composed
        audio_dropped = True

    if look is not None:
        graded = work_path(config, f"{stem}-3-look", ".mp4")
        apply_look(current, graded, look, config, runner, force=True)
        stages.append(Stage("look", graded))
        current = graded

    if audio_dropped and source_info.has_audio:
        voiced = work_path(config, f"{stem}-4-voice", ".mp4")
        attach_audio(current, resolved_source, voiced, config, force=True)
        stages.append(Stage("voice", voiced))
        current = voiced

    if music is not None:
        mixed = work_path(config, f"{stem}-5-music", ".mp4")
        add_music_bed(current, music, mixed, config, target_lufs=target_lufs, force=True)
        stages.append(Stage("music", mixed))
        current = mixed

    short = to_short(
        current, resolved_output, config, runner, aspect_ratio=aspect_ratio, force=force
    )
    stages.append(Stage("short", resolved_output))

    return PipelineResult(
        final=resolved_output,
        media=short.info,
        stages=tuple(stages),
        quality_report=short.quality_report,
        thumbnail_path=short.thumbnail_path,
    )
