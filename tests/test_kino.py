"""The single gateway to the kino CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import KinoError, KinoTimeoutError, MediaLabError
from media_lab.kino import KinoResult, KinoRunner, _extract_json_object, find_kino


def test_finds_the_kino_executable() -> None:
    assert find_kino().is_file()


def test_runs_a_real_command(config: Config) -> None:
    result = KinoRunner.from_config(config).run(["--version"])

    assert "1.15.1" in result.stdout
    assert result.duration_s >= 0


def test_puts_the_project_ffmpeg_on_path(config: Config) -> None:
    runner = KinoRunner.from_config(config)
    assert str(config.ffmpeg_dir) in runner._environment()["PATH"]


def test_raises_on_a_failing_command(config: Config) -> None:
    with pytest.raises(KinoError) as caught:
        KinoRunner.from_config(config).run(["info", "/nonexistent/clip.mp4"])

    assert caught.value.returncode != 0


def test_raises_on_timeout(config: Config, sample_video: Path) -> None:
    with pytest.raises(KinoTimeoutError, match="timed out"):
        KinoRunner.from_config(config).run(["doctor"], timeout_s=0)


def test_run_json_returns_a_mapping(config: Config, sample_video: Path) -> None:
    payload = KinoRunner.from_config(config).run_json(["info", str(sample_video)])

    assert isinstance(payload, dict)


def test_extract_json_tolerates_leading_noise() -> None:
    assert _extract_json_object('warning: x\n{"success": true}') == {"success": True}


def test_extract_json_rejects_output_without_an_object() -> None:
    with pytest.raises(MediaLabError, match="could not parse"):
        _extract_json_object("no json here")


def test_extract_json_rejects_a_bare_array() -> None:
    with pytest.raises(MediaLabError, match="expected a JSON object"):
        _extract_json_object("[1, 2, 3]")


def test_extract_json_rejects_malformed_json() -> None:
    with pytest.raises(MediaLabError, match="could not parse"):
        _extract_json_object('{"success": ')


def test_run_json_surfaces_a_reported_failure(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """kino can exit 0 while reporting failure in its JSON payload."""
    failure = KinoResult(
        args=("composite-layers",),
        stdout='{"success": false, "error": "bad spec"}',
        stderr="",
        duration_s=0.0,
    )
    monkeypatch.setattr(KinoRunner, "run", lambda self, args, timeout_s=None: failure)

    with pytest.raises(KinoError, match="bad spec"):
        KinoRunner.from_config(config).run_json(["composite-layers", "--spec", "x.json"])


def test_extract_json_skips_braces_in_leading_log_noise() -> None:
    """A warning line containing braces must not hide the real payload."""
    noisy = 'warn: layer {bad} skipped\n{"success": true, "data": {}}'

    assert _extract_json_object(noisy) == {"success": True, "data": {}}


def test_extract_json_handles_several_decoy_braces() -> None:
    noisy = '{oops\n{also bad\n{"ok": 1}'
    assert _extract_json_object(noisy) == {"ok": 1}
