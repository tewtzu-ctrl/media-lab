"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .config import Config, load_config
from .errors import MediaLabError
from .kino import KinoRunner


def _report_doctor(config: Config) -> int:
    runner = KinoRunner.from_config(config)
    print("media-lab environment")
    print(f"  root            {config.root}")
    print(f"  ffmpeg          {config.ffmpeg}")
    print(f"  ffprobe         {config.ffprobe}")
    print(f"  sources (in)    {config.in_dir}")
    print(f"  renders (out)   {config.out_dir}")
    print(f"  work            {config.work_dir}")
    print(f"  kino            {runner.executable}")
    print(f"  kino timeout    {config.kino_timeout_s}s")
    print(f"  hyperframes     {config.hyperframes_command or '(not configured)'}")
    print()
    print("kino doctor")
    result = runner.run(["doctor"])
    print(result.stdout.rstrip())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="media-lab",
        description="Local video and photo editing pipeline built on Kinocut.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor", help="Report the state of the local environment")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config()
        if args.command == "doctor":
            return _report_doctor(config)
    except MediaLabError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unhandled command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
