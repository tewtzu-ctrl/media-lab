"""Path safety: the non-destructive contract of the project.

Sources under `in/` are read-only. Renders land under `out/` or `work/`.
Nothing overwrites an existing file unless the caller says so explicitly.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .errors import PathSafetyError


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def ensure_readable_source(path: Path | str) -> Path:
    """Resolve an input file, or explain precisely why it is unusable."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise PathSafetyError(f"input does not exist: {resolved}")
    if not resolved.is_file():
        raise PathSafetyError(f"input is not a file: {resolved}")
    if resolved.stat().st_size == 0:
        raise PathSafetyError(f"input is empty: {resolved}")
    return resolved


def ensure_writable_output(path: Path | str, config: Config, *, force: bool = False) -> Path:
    """Resolve an output path, refusing anything that would destroy data."""
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = (config.root / resolved).resolve()
    else:
        resolved = resolved.resolve()

    if _is_within(resolved, config.in_dir):
        raise PathSafetyError(
            f"refusing to write inside the source directory {config.in_dir}: {resolved}"
        )
    if resolved.is_dir():
        raise PathSafetyError(f"output path is a directory: {resolved}")
    if resolved.exists() and not force:
        raise PathSafetyError(f"output already exists (pass force to overwrite): {resolved}")

    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def work_path(config: Config, stem: str, suffix: str) -> Path:
    """A path for a pipeline intermediate, kept for inspection."""
    if not suffix.startswith("."):
        raise PathSafetyError(f"suffix must start with a dot, got {suffix!r}")
    config.work_dir.mkdir(parents=True, exist_ok=True)
    return config.work_dir / f"{stem}{suffix}"
