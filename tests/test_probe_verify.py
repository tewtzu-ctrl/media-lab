"""The verification layer: nothing is reported done without passing here."""

from __future__ import annotations

from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import ProbeError, VerificationError
from media_lab.probe import probe
from media_lab.verify import Expectations, verify_render


def test_probe_reads_real_facts(sample_video: Path, config: Config) -> None:
    info = probe(sample_video, config)

    assert info.has_video is True
    assert info.has_audio is True
    assert (info.width, info.height) == (640, 360)
    assert info.fps == pytest.approx(25.0, abs=0.1)
    assert info.duration_s == pytest.approx(2.0, abs=0.2)


def test_probe_detects_absent_audio(silent_video: Path, config: Config) -> None:
    assert probe(silent_video, config).has_audio is False


def test_probe_rejects_a_corrupt_file(corrupt_file: Path, config: Config) -> None:
    with pytest.raises(ProbeError, match="ffprobe failed"):
        probe(corrupt_file, config)


def test_verify_accepts_a_matching_render(sample_video: Path, config: Config) -> None:
    info = verify_render(
        sample_video,
        config,
        Expectations(duration_s=2.0, width=640, height=360, requires_audio=True),
    )
    assert info.width == 640


def test_verify_reports_a_missing_file(config: Config) -> None:
    with pytest.raises(VerificationError, match="file was not created"):
        verify_render(config.out_dir / "never.mp4", config)


def test_verify_reports_a_truncated_file(config: Config) -> None:
    tiny = config.out_dir
    tiny.mkdir(parents=True, exist_ok=True)
    target = tiny / "tiny.mp4"
    target.write_bytes(b"0" * 10)

    with pytest.raises(VerificationError, match="only 10 bytes"):
        verify_render(target, config)


def test_verify_reports_wrong_duration(sample_video: Path, config: Config) -> None:
    with pytest.raises(VerificationError, match="duration is"):
        verify_render(sample_video, config, Expectations(duration_s=30.0))


def test_verify_reports_missing_audio(silent_video: Path, config: Config) -> None:
    with pytest.raises(VerificationError, match="no audio stream"):
        verify_render(silent_video, config, Expectations(requires_audio=True))


def test_verify_reports_unexpected_audio(sample_video: Path, config: Config) -> None:
    with pytest.raises(VerificationError, match="none expected"):
        verify_render(sample_video, config, Expectations(requires_audio=False))


def test_verify_reports_missing_alpha(sample_video: Path, config: Config) -> None:
    with pytest.raises(VerificationError, match="no alpha channel"):
        verify_render(sample_video, config, Expectations(requires_alpha=True))


def test_verify_reports_wrong_aspect_ratio(sample_video: Path, config: Config) -> None:
    with pytest.raises(VerificationError, match="aspect ratio is"):
        verify_render(sample_video, config, Expectations(aspect_ratio="9:16"))


def test_verify_rejects_an_unknown_aspect_ratio(sample_video: Path, config: Config) -> None:
    with pytest.raises(VerificationError, match="unknown aspect ratio"):
        verify_render(sample_video, config, Expectations(aspect_ratio="7:3"))


def test_verify_collects_every_problem_at_once(silent_video: Path, config: Config) -> None:
    with pytest.raises(VerificationError) as caught:
        verify_render(
            silent_video,
            config,
            Expectations(duration_s=99.0, width=1080, requires_audio=True),
        )
    assert len(caught.value.problems) == 3


def test_parse_fps_handles_rational_and_plain_values() -> None:
    from media_lab.probe import _parse_fps

    assert _parse_fps("30000/1001") == pytest.approx(29.97, abs=0.01)
    assert _parse_fps("25") == 25.0


def test_parse_fps_survives_garbage() -> None:
    from media_lab.probe import _parse_fps

    assert _parse_fps("0/0") == 0.0
    assert _parse_fps("not-a-rate") == 0.0
    assert _parse_fps("x/y") == 0.0


def test_parse_duration_falls_back_to_the_video_stream() -> None:
    from media_lab.probe import _parse_duration

    assert _parse_duration({"format": {}}, {"duration": "4.5"}) == 4.5
    assert _parse_duration({"format": {"duration": "bad"}}, {"duration": "2.0"}) == 2.0
    assert _parse_duration({"format": {}}, None) == 0.0


def test_media_info_aspect_ratio_guards_zero_height(sample_video: Path, config: Config) -> None:
    from dataclasses import replace

    info = replace(probe(sample_video, config), height=0)
    assert info.aspect_ratio == 0.0
