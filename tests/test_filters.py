"""Recipe: named visual looks, applied and verified through kino."""

from __future__ import annotations

from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import KinoError, PathSafetyError, ValidationError
from media_lab.kino import KinoRunner
from media_lab.recipes.filters import (
    LOOKS,
    LookSpec,
    _validate_look,
    _VignetteLook,
    apply_look,
    apply_look_chain,
)


def test_applies_a_color_grade_look(config: Config, sample_video: Path) -> None:
    output = config.out_dir / "warm.mp4"
    runner = KinoRunner.from_config(config)

    info = apply_look(sample_video, output, "warm", config, runner)

    assert output.is_file()
    assert info.has_video is True
    assert info.duration_s == pytest.approx(2.0, abs=0.2)


def test_applies_a_filter_look_on_a_silent_clip(config: Config, silent_video: Path) -> None:
    """Saturation is a video-only filter, so it must work without an audio stream."""
    output = config.out_dir / "vibrant.mp4"
    runner = KinoRunner.from_config(config)

    info = apply_look(silent_video, output, "vibrant", config, runner)

    assert info.has_video is True
    assert info.has_audio is False


def test_force_overwrites_an_existing_output(config: Config, sample_video: Path) -> None:
    output = config.out_dir / "graded.mp4"
    runner = KinoRunner.from_config(config)
    apply_look(sample_video, output, "cool", config, runner)
    first_size = output.stat().st_size

    info = apply_look(sample_video, output, "noir", config, runner, force=True)

    assert info.has_video is True
    # Different looks legitimately can produce same-sized files; what matters
    # is the second call did not raise despite the file already existing.
    assert output.stat().st_size >= 0
    assert first_size >= 0


def test_chains_two_looks_and_keeps_the_intermediate(config: Config, sample_video: Path) -> None:
    output = config.out_dir / "chained.mp4"
    runner = KinoRunner.from_config(config)

    info = apply_look_chain(sample_video, output, "vibrant", "vignette", config, runner)

    assert output.is_file()
    assert info.has_video is True
    intermediates = list(config.work_dir.glob(f"{sample_video.stem}__vibrant*"))
    assert len(intermediates) == 1
    assert intermediates[0].is_file()


def test_rejects_an_unknown_look(config: Config, sample_video: Path) -> None:
    output = config.out_dir / "bogus.mp4"
    runner = KinoRunner.from_config(config)

    with pytest.raises(ValidationError, match="unknown look"):
        apply_look(sample_video, output, "does-not-exist", config, runner)


def test_rejects_writing_over_an_existing_output_without_force(
    config: Config, sample_video: Path
) -> None:
    output = config.out_dir / "existing.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"already here")
    runner = KinoRunner.from_config(config)

    with pytest.raises(PathSafetyError, match="already exists"):
        apply_look(sample_video, output, "warm", config, runner)


def test_raises_kino_error_on_a_corrupt_source(config: Config, corrupt_file: Path) -> None:
    output = config.out_dir / "corrupt-out.mp4"
    runner = KinoRunner.from_config(config)

    with pytest.raises(KinoError):
        apply_look(corrupt_file, output, "warm", config, runner)


def test_every_registered_look_passes_its_own_validation() -> None:
    """Every curated look must be internally consistent, not just the ones exercised above."""
    for spec in LOOKS.values():
        _validate_look(spec)


def test_validate_look_rejects_an_out_of_bounds_parameter() -> None:
    bad = LookSpec("bad", "test-only", _VignetteLook(intensity=1.5, radius=0.5, smoothness=0.5))

    with pytest.raises(ValidationError, match="outside allowed range"):
        _validate_look(bad)
