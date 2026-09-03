# media-lab

Local video and photo editing pipeline for short social clips, built as a typed
wrapper over [Kinocut](https://github.com/KyaniteLabs/kinocut).

Everything runs on this machine. No cloud services, no API keys, no uploads.

- Working contract: [REGULI.md](./REGULI.md)
- Implementation plan: [PLAN.md](./PLAN.md)

## Requirements

| Component | Version | Notes |
|---|---|---|
| macOS | arm64 (Apple Silicon) | ffmpeg binaries are arm64 only |
| Python | 3.12 | installed automatically by `uv` |
| Node.js | 22+ | needed by the Hyperframes CLI |
| uv | any recent | https://docs.astral.sh/uv/ |

Pinned dependencies: `kinocut==1.15.1`, `hyperframes@0.8.27`,
static `ffmpeg`/`ffprobe` 9.0 (checksums pinned in `scripts/fetch-ffmpeg.sh`).

## Install

```sh
git clone <this repo> && cd media-lab
./scripts/fetch-ffmpeg.sh   # static ffmpeg + ffprobe into ./bin
make setup                  # uv sync + npm install
cp .env.example .env
make doctor                 # verify the environment
```

`bin/`, `.venv/` and `node_modules/` are gitignored; the three commands above
recreate them from pinned versions.

## Layout

```
bin/       static ffmpeg + ffprobe (gitignored, see scripts/fetch-ffmpeg.sh)
in/        source media - READ ONLY, never modified (gitignored)
out/       renders (gitignored)
work/      pipeline intermediates, kept for inspection (gitignored)
scripts/   setup helpers
src/       package source
tests/     test suite
```

## Development

```sh
make test        # pytest with coverage
make lint        # ruff
make typecheck   # mypy strict
make check       # all of the above
```

## Environment variables

All configuration lives in `.env`. See [.env.example](./.env.example) for the
full documented list. This project holds no secrets: the variables are
directory paths and timeouts only.
