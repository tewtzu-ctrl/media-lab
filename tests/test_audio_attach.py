"""Putting a voice track back onto a video the compositor stripped."""

from __future__ import annotations

from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import PathSafetyError, ValidationError
from media_lab.recipes.audio_attach import attach_audio

CLIP_SECONDS = 2.0


def test_takes_video_from_one_file_and_audio_from_another(
    silent_video: Path, sample_video: Path, config: Config
) -> None:
    info = attach_audio(silent_video, sample_video, config.out_dir / "voiced.mp4", config)

    assert info.has_video is True
    assert info.has_audio is True
    assert info.duration_s == pytest.approx(CLIP_SECONDS, abs=0.3)


def test_accepts_an_audio_only_donor(
    silent_video: Path, sample_music: Path, config: Config
) -> None:
    info = attach_audio(silent_video, sample_music, config.out_dir / "voiced.mp4", config)
    assert info.has_audio is True


def test_rejects_a_video_without_a_video_stream(
    sample_music: Path, sample_video: Path, config: Config
) -> None:
    with pytest.raises(ValidationError, match="no video stream to keep"):
        attach_audio(sample_music, sample_video, config.out_dir / "v.mp4", config)


def test_rejects_a_donor_without_audio(silent_video: Path, config: Config) -> None:
    with pytest.raises(ValidationError, match="no audio stream to take"):
        attach_audio(silent_video, silent_video, config.out_dir / "v.mp4", config)


def test_refuses_to_overwrite_without_force(
    silent_video: Path, sample_video: Path, config: Config
) -> None:
    target = config.out_dir / "voiced.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"already here")

    with pytest.raises(PathSafetyError, match="already exists"):
        attach_audio(silent_video, sample_video, target, config)


def test_rejects_a_missing_donor(silent_video: Path, config: Config) -> None:
    with pytest.raises(PathSafetyError, match="does not exist"):
        attach_audio(silent_video, config.in_dir / "gone.mp4", config.out_dir / "v.mp4", config)
