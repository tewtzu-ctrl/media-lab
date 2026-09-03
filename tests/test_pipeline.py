"""The whole edit, end to end. Every stage runs for real."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import MediaLabError, PathSafetyError, ValidationError
from media_lab.kino import KinoRunner
from media_lab.pipeline import run_pipeline

TINY_WIDTH = 160
TINY_HEIGHT = 120
TINY_FPS = 5
TINY_SECONDS = 1


def _ffmpeg(config: Config, args: list[str]) -> None:
    subprocess.run(
        [str(config.ffmpeg), "-y", "-loglevel", "error", *args], check=True, capture_output=True
    )


@pytest.fixture
def runner(config: Config) -> KinoRunner:
    return KinoRunner.from_config(config)


@pytest.fixture
def tiny_source(config: Config) -> Path:
    """Small enough that a full cutout pass stays quick."""
    path = config.in_dir / "src.mp4"
    _ffmpeg(
        config,
        [
            "-f",
            "lavfi",
            "-i",
            f"testsrc=size={TINY_WIDTH}x{TINY_HEIGHT}:rate={TINY_FPS}:duration={TINY_SECONDS}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={TINY_SECONDS}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
    )
    return path


@pytest.fixture
def tiny_backdrop(config: Config) -> Path:
    path = config.in_dir / "bg.png"
    _ffmpeg(
        config,
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=teal:size={TINY_WIDTH}x{TINY_HEIGHT}:duration=1",
            "-frames:v",
            "1",
            str(path),
        ],
    )
    return path


def test_runs_every_stage_and_exports_vertical(
    tiny_source: Path, tiny_backdrop: Path, sample_music: Path, config: Config, runner: KinoRunner
) -> None:
    result = run_pipeline(
        tiny_source,
        config.out_dir / "final.mp4",
        config,
        runner,
        backdrop=tiny_backdrop,
        look="cinematic",
        music=sample_music,
    )

    assert [stage.name for stage in result.stages] == [
        "cutout",
        "backdrop",
        "look",
        "voice",
        "music",
        "short",
    ]
    assert result.media.width / result.media.height == pytest.approx(9 / 16, abs=0.02)
    assert result.media.has_audio is True
    assert result.final.is_file()


def test_keeps_every_intermediate_for_inspection(
    tiny_source: Path, tiny_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    result = run_pipeline(
        tiny_source, config.out_dir / "final.mp4", config, runner, backdrop=tiny_backdrop
    )
    for stage in result.stages[:-1]:
        assert stage.output.is_file(), f"{stage.name} intermediate is missing"


def test_never_touches_the_source_directory(
    tiny_source: Path, tiny_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    before = {path: path.read_bytes() for path in sorted(config.in_dir.iterdir())}

    run_pipeline(tiny_source, config.out_dir / "final.mp4", config, runner, backdrop=tiny_backdrop)

    after = {path: path.read_bytes() for path in sorted(config.in_dir.iterdir())}
    assert before == after


def test_skips_cutout_and_backdrop_when_no_backdrop_is_given(
    tiny_source: Path, config: Config, runner: KinoRunner
) -> None:
    result = run_pipeline(tiny_source, config.out_dir / "final.mp4", config, runner, look="noir")

    assert [stage.name for stage in result.stages] == ["look", "short"]
    assert result.media.has_audio is True


def test_keeps_the_original_audio_when_only_reframing(
    tiny_source: Path, config: Config, runner: KinoRunner
) -> None:
    result = run_pipeline(tiny_source, config.out_dir / "final.mp4", config, runner)

    assert [stage.name for stage in result.stages] == ["short"]
    assert result.media.has_audio is True


def test_stops_at_the_failing_stage_and_keeps_what_ran(
    tiny_source: Path, tiny_backdrop: Path, config: Config, runner: KinoRunner
) -> None:
    """An unusable music file must fail after the earlier stages have landed."""
    broken_music = config.in_dir / "not-music.txt"
    broken_music.write_text("no audio here", encoding="utf-8")

    with pytest.raises(MediaLabError):
        run_pipeline(
            tiny_source,
            config.out_dir / "final.mp4",
            config,
            runner,
            backdrop=tiny_backdrop,
            music=broken_music,
        )

    assert (config.work_dir / "final-1-cutout.webm").is_file()
    assert (config.work_dir / "final-2-backdrop.mp4").is_file()
    assert not (config.out_dir / "final.mp4").exists()


def test_refuses_to_overwrite_an_existing_final_render(
    tiny_source: Path, config: Config, runner: KinoRunner
) -> None:
    target = config.out_dir / "final.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"already here")

    with pytest.raises(PathSafetyError, match="already exists"):
        run_pipeline(tiny_source, target, config, runner)


def test_rejects_an_unknown_look(tiny_source: Path, config: Config, runner: KinoRunner) -> None:
    with pytest.raises(ValidationError):
        run_pipeline(tiny_source, config.out_dir / "final.mp4", config, runner, look="disco")
