"""Compositing a cutout onto a new backdrop."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import MediaLabError, PathSafetyError
from media_lab.kino import KinoRunner
from media_lab.recipes.backdrop import place_on_backdrop

CANVAS_WIDTH = 320
CANVAS_HEIGHT = 240
SUBJECT_FPS = 10
SUBJECT_SECONDS = 1


def _ffmpeg(config: Config, args: list[str]) -> None:
    subprocess.run(
        [str(config.ffmpeg), "-y", "-loglevel", "error", *args], check=True, capture_output=True
    )


@pytest.fixture
def runner(config: Config) -> KinoRunner:
    return KinoRunner.from_config(config)


@pytest.fixture
def subject(config: Config) -> Path:
    """A transparent subject clip, standing in for a real cutout."""
    path = config.in_dir / "subject.mov"
    _ffmpeg(
        config,
        [
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size=200x150:rate={SUBJECT_FPS}:duration={SUBJECT_SECONDS}",
            "-vf",
            "format=yuva444p10le",
            "-c:v",
            "prores_ks",
            "-profile:v",
            "4444",
            str(path),
        ],
    )
    return path


@pytest.fixture
def still_backdrop(config: Config) -> Path:
    path = config.in_dir / "bg.png"
    _ffmpeg(
        config,
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=navy:size={CANVAS_WIDTH}x{CANVAS_HEIGHT}:duration=1",
            "-frames:v",
            "1",
            str(path),
        ],
    )
    return path


@pytest.fixture
def short_video_backdrop(config: Config) -> Path:
    """A moving backdrop that ends before the subject does."""
    path = config.in_dir / "bg-short.mp4"
    _ffmpeg(
        config,
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=green:size={CANVAS_WIDTH}x{CANVAS_HEIGHT}:rate=10:duration=0.4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
    )
    return path


def test_composites_onto_a_still_backdrop(
    subject: Path, still_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    result = place_on_backdrop(subject, still_backdrop, config.out_dir / "c.mp4", config, runner)

    assert (result.canvas_width, result.canvas_height) == (CANVAS_WIDTH, CANVAS_HEIGHT)
    assert result.media.duration_s == pytest.approx(SUBJECT_SECONDS, abs=0.3)
    assert result.media.has_audio is False
    assert result.backdrop_was_shorter is False


def test_writes_an_inspectable_spec(
    subject: Path, still_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    result = place_on_backdrop(subject, still_backdrop, config.out_dir / "c.mp4", config, runner)
    spec = json.loads(result.spec_path.read_text(encoding="utf-8"))

    assert spec["canvas"]["width"] == CANVAS_WIDTH
    assert [layer["id"] for layer in spec["layers"]] == ["backdrop", "subject"]
    assert not Path(spec["layers"][0]["src"]).is_absolute()


def test_reports_a_backdrop_that_runs_out_early(
    subject: Path, short_video_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    result = place_on_backdrop(
        subject, short_video_backdrop, config.out_dir / "c.mp4", config, runner
    )
    assert result.backdrop_was_shorter is True


def test_canvas_size_can_be_overridden(
    subject: Path, still_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    result = place_on_backdrop(
        subject, still_backdrop, config.out_dir / "c.mp4", config, runner, width=160, height=120
    )
    assert (result.media.width, result.media.height) == (160, 120)


def test_rejects_an_out_of_range_scale(
    subject: Path, still_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    with pytest.raises(MediaLabError, match="scale must be between"):
        place_on_backdrop(
            subject, still_backdrop, config.out_dir / "c.mp4", config, runner, scale=99.0
        )


def test_rejects_an_out_of_range_opacity(
    subject: Path, still_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    with pytest.raises(MediaLabError, match="opacity must be between"):
        place_on_backdrop(
            subject, still_backdrop, config.out_dir / "c.mp4", config, runner, opacity=4.0
        )


def test_rejects_a_subject_without_video(
    sample_music: Path, still_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    with pytest.raises(MediaLabError, match="no video stream"):
        place_on_backdrop(sample_music, still_backdrop, config.out_dir / "c.mp4", config, runner)


def test_rejects_a_missing_backdrop(subject: Path, config: Config, runner: KinoRunner) -> None:
    with pytest.raises(PathSafetyError, match="does not exist"):
        place_on_backdrop(
            subject, config.in_dir / "absent.png", config.out_dir / "c.mp4", config, runner
        )
