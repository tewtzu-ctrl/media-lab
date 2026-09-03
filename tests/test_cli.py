"""The command line surface."""

from __future__ import annotations

import argparse
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


def test_every_recipe_has_a_handler() -> None:
    """A subcommand without a handler would fail only at runtime."""
    parser = cli.build_parser()
    actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    names = set(actions[0].choices)

    assert names == set(cli.HANDLERS) | {"doctor"}


def test_pipeline_command_accepts_the_full_option_set() -> None:
    args = cli.build_parser().parse_args(
        [
            "pipeline",
            "clip.mp4",
            "-o",
            "out.mp4",
            "--bg",
            "bg.png",
            "--look",
            "noir",
            "--track",
            "song.mp3",
            "--aspect",
            "9:16",
        ]
    )

    assert args.command == "pipeline"
    assert (args.bg, args.look, args.track) == ("bg.png", "noir", "song.mp3")


def test_filter_command_rejects_an_unknown_look() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["filter", "c.mp4", "-o", "o.mp4", "--look", "disco"])


def test_music_command_defaults_to_looping_the_bed() -> None:
    args = cli.build_parser().parse_args(["music", "c.mp4", "-o", "o.mp4", "--track", "s.mp3"])
    assert args.loop is True

    args = cli.build_parser().parse_args(
        ["music", "c.mp4", "-o", "o.mp4", "--track", "s.mp3", "--no-loop"]
    )
    assert args.loop is False


def test_cutout_reports_a_failure_as_a_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)

    assert cli.main(["cutout", "in/definitely-absent.mp4", "-o", "out/x.webm"]) == 1
    assert "does not exist" in capsys.readouterr().err
