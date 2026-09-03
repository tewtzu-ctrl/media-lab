"""The non-destructive contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from media_lab.config import Config
from media_lab.errors import PathSafetyError
from media_lab.paths import (
    clear_work_directory,
    ensure_readable_source,
    ensure_writable_output,
    work_path,
)


def test_accepts_an_existing_file(sample_video: Path) -> None:
    assert ensure_readable_source(sample_video) == sample_video.resolve()


def test_rejects_missing_input(tmp_path: Path) -> None:
    with pytest.raises(PathSafetyError, match="does not exist"):
        ensure_readable_source(tmp_path / "absent.mp4")


def test_rejects_directory_as_input(tmp_path: Path) -> None:
    with pytest.raises(PathSafetyError, match="not a file"):
        ensure_readable_source(tmp_path)


def test_rejects_empty_input(tmp_path: Path) -> None:
    empty = tmp_path / "empty.mp4"
    empty.touch()
    with pytest.raises(PathSafetyError, match="is empty"):
        ensure_readable_source(empty)


def test_creates_parent_directories_for_output(config: Config) -> None:
    target = ensure_writable_output(config.out_dir / "nested" / "clip.mp4", config)
    assert target.parent.is_dir()


def test_refuses_to_write_into_the_source_directory(config: Config) -> None:
    with pytest.raises(PathSafetyError, match="source directory"):
        ensure_writable_output(config.in_dir / "clip.mp4", config)


def test_refuses_to_overwrite_without_force(config: Config) -> None:
    existing = config.out_dir / "clip.mp4"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"x")

    with pytest.raises(PathSafetyError, match="already exists"):
        ensure_writable_output(existing, config)


def test_overwrites_when_forced(config: Config) -> None:
    existing = config.out_dir / "clip.mp4"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"x")

    assert ensure_writable_output(existing, config, force=True) == existing.resolve()


def test_rejects_directory_as_output(config: Config) -> None:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(PathSafetyError, match="is a directory"):
        ensure_writable_output(config.out_dir, config)


def test_work_path_requires_a_dotted_suffix(config: Config) -> None:
    with pytest.raises(PathSafetyError, match="start with a dot"):
        work_path(config, "stage", "mp4")


def test_work_path_lands_in_the_work_directory(config: Config) -> None:
    assert work_path(config, "stage", ".mp4") == config.work_dir / "stage.mp4"


def test_refuses_to_write_outside_the_project(config: Config, tmp_path: Path) -> None:
    """An absolute path elsewhere on disk must not become a render target."""
    outside = tmp_path.parent / "escaped.mp4"

    with pytest.raises(PathSafetyError, match="outside the project"):
        ensure_writable_output(outside, config)


def test_refuses_a_relative_path_that_climbs_out(config: Config) -> None:
    with pytest.raises(PathSafetyError, match="outside the project"):
        ensure_writable_output("../../escaped.mp4", config)


def test_accepts_a_path_under_the_work_directory(config: Config) -> None:
    target = ensure_writable_output(config.work_dir / "stage.mp4", config)
    assert target.parent == config.work_dir


def test_work_directory_is_created_and_reusable(config: Config) -> None:
    from media_lab.paths import work_directory

    first = work_directory(config, "stage.d")
    second = work_directory(config, "stage.d")

    assert first == second
    assert first.is_dir()


def test_work_directory_rejects_an_empty_name(config: Config) -> None:
    from media_lab.paths import work_directory

    with pytest.raises(PathSafetyError, match="must not be empty"):
        work_directory(config, "")


def test_clear_work_directory_removes_files_and_subdirectories(config: Config) -> None:
    (config.work_dir / "sub").mkdir(parents=True, exist_ok=True)
    (config.work_dir / "a.txt").write_bytes(b"hello")
    (config.work_dir / "sub" / "b.txt").write_bytes(b"world!")

    entries, total_bytes = clear_work_directory(config)

    assert {e.name for e in entries} == {"a.txt", "sub"}
    assert total_bytes == len(b"hello") + len(b"world!")
    assert list(config.work_dir.iterdir()) == []


def test_clear_work_directory_dry_run_removes_nothing(config: Config) -> None:
    config.work_dir.mkdir(parents=True, exist_ok=True)
    (config.work_dir / "a.txt").write_bytes(b"hello")

    entries, total_bytes = clear_work_directory(config, dry_run=True)

    assert [e.name for e in entries] == ["a.txt"]
    assert total_bytes == 5
    assert (config.work_dir / "a.txt").is_file()


def test_clear_work_directory_on_an_absent_directory_is_a_noop(config: Config) -> None:
    assert not config.work_dir.exists()

    entries, total_bytes = clear_work_directory(config)

    assert entries == ()
    assert total_bytes == 0


def test_clear_work_directory_on_an_already_empty_directory(config: Config) -> None:
    config.work_dir.mkdir(parents=True, exist_ok=True)

    entries, total_bytes = clear_work_directory(config)

    assert entries == ()
    assert total_bytes == 0


def test_clear_work_directory_never_touches_in_or_out(config: Config) -> None:
    (config.in_dir / "source.mp4").write_bytes(b"do not touch")
    config.out_dir.mkdir(parents=True, exist_ok=True)
    (config.out_dir / "final.mp4").write_bytes(b"do not touch either")
    (config.work_dir / "scratch.tmp").mkdir(parents=True, exist_ok=True)

    clear_work_directory(config)

    assert (config.in_dir / "source.mp4").read_bytes() == b"do not touch"
    assert (config.out_dir / "final.mp4").read_bytes() == b"do not touch either"
