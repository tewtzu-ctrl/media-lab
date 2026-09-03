"""The command line surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from media_lab import cli


def test_doctor_reports_the_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], bin_dir: Path
) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)

    assert cli.main(["doctor"]) == 0

    printed = capsys.readouterr().out
    assert "media-lab environment" in printed
    assert "kino doctor" in printed


def test_reports_configuration_failures_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    assert cli.main(["doctor"]) == 1
    assert "error:" in capsys.readouterr().err


def test_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit):
        cli.main([])


def test_parser_exposes_the_doctor_command() -> None:
    assert cli.build_parser().prog == "media-lab"
