"""Config is validated at startup, loudly."""

from __future__ import annotations

from pathlib import Path

import pytest

from media_lab.config import load_config, read_env_file
from media_lab.errors import ConfigError

REPO_BIN = Path(__file__).resolve().parent.parent / "bin"


def _env(**overrides: str) -> dict[str, str]:
    base = {"MEDIA_LAB_FFMPEG_DIR": str(REPO_BIN)}
    base.update(overrides)
    return base


def test_loads_valid_configuration(tmp_path: Path, bin_dir: Path) -> None:
    (tmp_path / "in").mkdir()
    config = load_config(root=tmp_path, env=_env())

    assert config.ffmpeg_dir == bin_dir
    assert config.out_dir.is_dir()
    assert config.work_dir.is_dir()
    assert config.kino_timeout_s == 1800


def test_rejects_missing_ffmpeg(tmp_path: Path) -> None:
    (tmp_path / "in").mkdir()
    empty = tmp_path / "nowhere"
    empty.mkdir()

    with pytest.raises(ConfigError, match="fetch-ffmpeg"):
        load_config(root=tmp_path, env=_env(MEDIA_LAB_FFMPEG_DIR=str(empty)))


def test_rejects_missing_source_directory(tmp_path: Path, bin_dir: Path) -> None:
    with pytest.raises(ConfigError, match="source directory does not exist"):
        load_config(root=tmp_path, env=_env())


def test_rejects_non_numeric_timeout(tmp_path: Path, bin_dir: Path) -> None:
    (tmp_path / "in").mkdir()
    with pytest.raises(ConfigError, match="whole number"):
        load_config(root=tmp_path, env=_env(MEDIA_LAB_KINO_TIMEOUT_S="soon"))


def test_rejects_zero_timeout(tmp_path: Path, bin_dir: Path) -> None:
    (tmp_path / "in").mkdir()
    with pytest.raises(ConfigError, match="at least 1"):
        load_config(root=tmp_path, env=_env(MEDIA_LAB_KINO_TIMEOUT_S="0"))


def test_reads_env_file_and_ignores_comments(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "# a comment\n\nMEDIA_LAB_IN_DIR='./sources'\nBROKEN\nX=1\n", encoding="utf-8"
    )
    values = read_env_file(tmp_path / ".env")

    assert values == {"MEDIA_LAB_IN_DIR": "./sources", "X": "1"}


def test_missing_env_file_is_not_an_error(tmp_path: Path) -> None:
    assert read_env_file(tmp_path / ".env") == {}


def test_config_is_immutable(tmp_path: Path, bin_dir: Path) -> None:
    (tmp_path / "in").mkdir()
    config = load_config(root=tmp_path, env=_env())

    with pytest.raises(AttributeError):
        config.kino_timeout_s = 5  # type: ignore[misc]
