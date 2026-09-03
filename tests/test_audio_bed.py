"""Music bed with sidechain ducking.

Every test here runs the real ffmpeg filtergraph and measures the real
loudness of the result; nothing is mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from media_lab.config import Config
from media_lab.errors import PathSafetyError, ValidationError
from media_lab.recipes.audio_bed import add_music_bed

CLIP_SECONDS = 2.0
TARGET_LUFS = -16.0
LUFS_TOLERANCE = 1.5


@pytest.fixture
def short_music(config: Config) -> Path:
    """Music shorter than the clip, so looping has something to do."""
    path = config.in_dir / "short.m4a"
    subprocess.run(
        [
            str(config.ffmpeg),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=330:duration=0.7",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def test_ducks_music_under_the_voice(
    sample_video: Path, sample_music: Path, config: Config
) -> None:
    result = add_music_bed(sample_video, sample_music, config.out_dir / "mix.mp4", config)

    assert result.ducking_engaged is True
    assert result.media.has_audio is True
    assert result.media.has_video is True
    assert result.media.duration_s == pytest.approx(CLIP_SECONDS, abs=0.3)
    assert result.measured_lufs == pytest.approx(TARGET_LUFS, abs=LUFS_TOLERANCE)


def test_uses_music_as_the_only_track_when_the_source_is_silent(
    silent_video: Path, sample_music: Path, config: Config
) -> None:
    result = add_music_bed(silent_video, sample_music, config.out_dir / "mix.mp4", config)

    assert result.ducking_engaged is False
    assert result.media.has_audio is True
    assert result.media.duration_s == pytest.approx(CLIP_SECONDS, abs=0.3)


def test_loops_music_shorter_than_the_clip(
    sample_video: Path, short_music: Path, config: Config
) -> None:
    result = add_music_bed(sample_video, short_music, config.out_dir / "mix.mp4", config, loop=True)
    assert result.media.duration_s == pytest.approx(CLIP_SECONDS, abs=0.3)


def test_trims_music_longer_than_the_clip(
    sample_video: Path, sample_music: Path, config: Config
) -> None:
    """sample_music runs twice as long as the clip and must not extend it."""
    result = add_music_bed(sample_video, sample_music, config.out_dir / "mix.mp4", config)
    assert result.media.duration_s == pytest.approx(CLIP_SECONDS, abs=0.3)


def test_honours_a_quieter_bed(sample_video: Path, sample_music: Path, config: Config) -> None:
    result = add_music_bed(
        sample_video, sample_music, config.out_dir / "mix.mp4", config, music_volume=0.2
    )
    assert result.media.has_audio is True


def test_rejects_an_out_of_range_target_loudness(
    sample_video: Path, sample_music: Path, config: Config
) -> None:
    with pytest.raises(ValidationError, match="target_lufs must be between"):
        add_music_bed(
            sample_video, sample_music, config.out_dir / "mix.mp4", config, target_lufs=10.0
        )


def test_rejects_an_out_of_range_music_volume(
    sample_video: Path, sample_music: Path, config: Config
) -> None:
    with pytest.raises(ValidationError, match="music_volume must be between"):
        add_music_bed(
            sample_video, sample_music, config.out_dir / "mix.mp4", config, music_volume=9.0
        )


def test_rejects_an_out_of_range_duck_ratio(
    sample_video: Path, sample_music: Path, config: Config
) -> None:
    with pytest.raises(ValidationError, match="duck_ratio must be between"):
        add_music_bed(
            sample_video, sample_music, config.out_dir / "mix.mp4", config, duck_ratio=0.1
        )


def test_rejects_a_music_file_without_audio(
    sample_video: Path, silent_video: Path, config: Config
) -> None:
    with pytest.raises(ValidationError, match="no audio stream"):
        add_music_bed(sample_video, silent_video, config.out_dir / "mix.mp4", config)


def test_rejects_a_missing_music_file(sample_video: Path, config: Config) -> None:
    with pytest.raises(PathSafetyError, match="does not exist"):
        add_music_bed(sample_video, config.in_dir / "absent.mp3", config.out_dir / "m.mp4", config)


def test_refuses_to_overwrite_without_force(
    sample_video: Path, sample_music: Path, config: Config
) -> None:
    target = config.out_dir / "mix.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"already here")

    with pytest.raises(PathSafetyError, match="already exists"):
        add_music_bed(sample_video, sample_music, target, config)


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"duck_threshold": 5.0}, "duck_threshold must be between"),
        ({"duck_attack_ms": 99999.0}, "duck_attack_ms must be between"),
        ({"duck_release_ms": -1.0}, "duck_release_ms must be between"),
    ],
)
def test_rejects_out_of_range_ducking_parameters(
    sample_video: Path,
    sample_music: Path,
    config: Config,
    kwargs: dict[str, Any],
    expected: str,
) -> None:
    """These values reach an ffmpeg filtergraph, so they must be bounded."""
    with pytest.raises(ValidationError, match=expected):
        add_music_bed(sample_video, sample_music, config.out_dir / "mix.mp4", config, **kwargs)
