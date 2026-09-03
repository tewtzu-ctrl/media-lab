"""The `short` recipe: vertical export plus quality gate."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import MediaLabError, PathSafetyError, VerificationError
from media_lab.kino import KinoRunner
from media_lab.recipes.to_short import QualityCheck, QualityReport, to_short

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "bin"
CLIP_SECONDS = 2
CLIP_FPS = 25
VERTICAL_WIDTH = 360
VERTICAL_HEIGHT = 640
SQUARE_SIZE = 480
NINE_SIXTEEN = 9 / 16
ASPECT_TOLERANCE = 0.02


def _build_clip(path: Path, width: int, height: int) -> None:
    """Build a short clip at an arbitrary resolution with a real ffmpeg call."""
    command = [
        str(BIN_DIR / "ffmpeg"),
        "-y",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size={width}x{height}:rate={CLIP_FPS}:duration={CLIP_SECONDS}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={CLIP_SECONDS}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"fixture ffmpeg failed: {completed.stderr.strip()}")


@pytest.fixture
def runner(config: Config) -> KinoRunner:
    return KinoRunner.from_config(config)


@pytest.fixture
def vertical_video(config: Config) -> Path:
    """A source clip that is already 9:16 before any resize."""
    path = config.in_dir / "vertical.mp4"
    _build_clip(path, VERTICAL_WIDTH, VERTICAL_HEIGHT)
    return path


@pytest.fixture
def square_video(config: Config) -> Path:
    """A source clip with a 1:1 aspect ratio."""
    path = config.in_dir / "square.mp4"
    _build_clip(path, SQUARE_SIZE, SQUARE_SIZE)
    return path


def test_to_short_renders_a_vertical_short_from_a_16_9_source(
    sample_video: Path, config: Config, runner: KinoRunner
) -> None:
    output = config.out_dir / "short.mp4"

    result = to_short(sample_video, output, config, runner)

    assert result.info.aspect_ratio == pytest.approx(NINE_SIXTEEN, abs=ASPECT_TOLERANCE)
    assert result.thumbnail_path == output.with_suffix(".jpg").resolve()
    assert result.thumbnail_path is not None
    assert result.thumbnail_path.is_file()
    assert result.thumbnail_path.stat().st_size > 0
    assert isinstance(result.quality_report, QualityReport)
    assert result.quality_report.checks
    assert all(isinstance(check, QualityCheck) for check in result.quality_report.checks)
    # The quality gate can fail without raising: warnings are surfaced, not hidden.
    assert result.quality_report.recommendations or result.quality_report.all_passed


def test_to_short_reframes_an_already_vertical_source(
    vertical_video: Path, config: Config, runner: KinoRunner
) -> None:
    output = config.out_dir / "from_vertical.mp4"

    result = to_short(vertical_video, output, config, runner, thumbnail=False)

    assert result.info.aspect_ratio == pytest.approx(NINE_SIXTEEN, abs=ASPECT_TOLERANCE)
    assert result.thumbnail_path is None


def test_to_short_reframes_a_square_source(
    square_video: Path, config: Config, runner: KinoRunner
) -> None:
    output = config.out_dir / "from_square.mp4"

    result = to_short(square_video, output, config, runner, thumbnail=False)

    assert result.info.aspect_ratio == pytest.approx(NINE_SIXTEEN, abs=ASPECT_TOLERANCE)


def test_to_short_skips_thumbnail_when_disabled(
    sample_video: Path, config: Config, runner: KinoRunner
) -> None:
    output = config.out_dir / "short_no_thumb.mp4"

    result = to_short(sample_video, output, config, runner, thumbnail=False)

    assert result.thumbnail_path is None
    assert not output.with_suffix(".jpg").exists()


def test_to_short_raises_when_quality_gate_fails_and_fail_on_warning_is_set(
    sample_video: Path, config: Config, runner: KinoRunner
) -> None:
    """The synthetic fixture clip is quiet and near-static, so the gate fails for real."""
    output = config.out_dir / "short_gated.mp4"

    with pytest.raises(VerificationError, match="did not match expectations") as caught:
        to_short(sample_video, output, config, runner, fail_on_warning=True)

    assert caught.value.problems


def test_to_short_rejects_an_unsupported_aspect_ratio(
    sample_video: Path, config: Config, runner: KinoRunner
) -> None:
    output = config.out_dir / "short_bad_ratio.mp4"

    with pytest.raises(MediaLabError, match="unsupported aspect ratio"):
        to_short(sample_video, output, config, runner, aspect_ratio="3:5")


def test_to_short_rejects_an_unsupported_quality(
    sample_video: Path, config: Config, runner: KinoRunner
) -> None:
    output = config.out_dir / "short_bad_quality.mp4"

    with pytest.raises(MediaLabError, match="unsupported quality"):
        to_short(sample_video, output, config, runner, quality="mega")


def test_to_short_refuses_to_overwrite_an_existing_output_without_force(
    sample_video: Path, config: Config, runner: KinoRunner
) -> None:
    output = config.out_dir / "short_once.mp4"
    to_short(sample_video, output, config, runner, thumbnail=False)

    with pytest.raises(PathSafetyError, match="already exists"):
        to_short(sample_video, output, config, runner, thumbnail=False)
