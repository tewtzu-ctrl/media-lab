"""Person cutout, including the alpha guarantee."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import MediaLabError, PathSafetyError
from media_lab.kino import KinoRunner
from media_lab.recipes.cutout import OBJECT_MODEL, cut_out_person

TINY_WIDTH = 160
TINY_HEIGHT = 120
TINY_FPS = 6
TINY_SECONDS = 1


@pytest.fixture
def tiny_clip(config: Config) -> Path:
    """A deliberately small clip: cutout costs roughly 125ms per frame."""
    path = config.in_dir / "tiny.mp4"
    subprocess.run(
        [
            str(config.ffmpeg),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={TINY_WIDTH}x{TINY_HEIGHT}:rate={TINY_FPS}:duration={TINY_SECONDS}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture
def tiny_still(config: Config) -> Path:
    path = config.in_dir / "tiny.png"
    subprocess.run(
        [
            str(config.ffmpeg),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={TINY_WIDTH}x{TINY_HEIGHT}:duration=1",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture
def runner(config: Config) -> KinoRunner:
    return KinoRunner.from_config(config)


def test_produces_a_cutout_with_alpha(tiny_clip: Path, config: Config, runner: KinoRunner) -> None:
    result = cut_out_person(tiny_clip, config.out_dir / "cut.mov", config, runner, quality="fast")

    assert result.media.has_alpha is True
    assert result.model == "u2net_human_seg"
    assert result.frames_processed > 0
    assert result.media.width == TINY_WIDTH


def test_handles_a_still_image(tiny_still: Path, config: Config, runner: KinoRunner) -> None:
    result = cut_out_person(tiny_still, config.out_dir / "cut.png", config, runner, quality="fast")

    assert result.media.has_alpha is True
    assert result.is_still is True


def test_rejects_a_video_output_suffix_for_a_still(
    tiny_still: Path, config: Config, runner: KinoRunner
) -> None:
    with pytest.raises(MediaLabError, match="must be written as .png"):
        cut_out_person(tiny_still, config.out_dir / "cut.mov", config, runner)


def test_rejects_a_still_output_suffix_for_a_video(
    tiny_clip: Path, config: Config, runner: KinoRunner
) -> None:
    with pytest.raises(MediaLabError, match="must be written as .mov"):
        cut_out_person(tiny_clip, config.out_dir / "cut.png", config, runner)


def test_rejects_an_unknown_quality(tiny_clip: Path, config: Config, runner: KinoRunner) -> None:
    with pytest.raises(MediaLabError, match="quality must be one of"):
        cut_out_person(tiny_clip, config.out_dir / "cut.mov", config, runner, quality="perfect")


def test_rejects_an_unknown_device(tiny_clip: Path, config: Config, runner: KinoRunner) -> None:
    with pytest.raises(MediaLabError, match="device must be one of"):
        cut_out_person(tiny_clip, config.out_dir / "cut.mov", config, runner, device="tpu")


def test_refuses_to_overwrite_an_existing_render(
    tiny_clip: Path, config: Config, runner: KinoRunner
) -> None:
    target = config.out_dir / "cut.mov"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"already here")

    with pytest.raises(PathSafetyError, match="already exists"):
        cut_out_person(tiny_clip, target, config, runner)


def test_rejects_a_missing_source(config: Config, runner: KinoRunner) -> None:
    with pytest.raises(PathSafetyError, match="does not exist"):
        cut_out_person(config.in_dir / "absent.mp4", config.out_dir / "c.webm", config, runner)


def test_object_model_is_named_but_not_offered() -> None:
    """Object cutouts need kinocut[object-matte], which this project does not install."""
    assert OBJECT_MODEL == "birefnet-general"


def test_rejects_a_payload_with_a_renamed_field() -> None:
    """A kinocut field rename must surface, not be silently defaulted to zero."""
    from media_lab.recipes.cutout import _require_number, _require_str

    with pytest.raises(MediaLabError, match="is not a number"):
        _require_number({"frames_processed": 10}, "framesProcessed")
    with pytest.raises(MediaLabError, match="is not a string"):
        _require_str({"model": None}, "model")


def test_rejects_a_boolean_where_a_number_is_expected() -> None:
    from media_lab.recipes.cutout import _require_number

    with pytest.raises(MediaLabError, match="is not a number"):
        _require_number({"framesProcessed": True}, "framesProcessed")
