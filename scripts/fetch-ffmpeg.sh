#!/usr/bin/env bash
# Fetch pinned static ffmpeg/ffprobe (macOS arm64) into ./bin.
# Binaries are gitignored because they are large and platform specific;
# this script makes the setup reproducible.
set -euo pipefail

FFMPEG_URL="https://www.osxexperts.net/ffmpeg9arm.zip"
FFPROBE_URL="https://www.osxexperts.net/ffprobe9arm.zip"
FFMPEG_SHA256="591260c945d0eef150e3bf82b0ef988bd36a9cecc18ff05d6679617159f0a95e"
FFPROBE_SHA256="e11c17e8200b3ee4c4c186d245e2b4053f01d56957336c1817fca0b997469106"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "error: these binaries are macOS arm64 only (got $(uname -s)/$(uname -m))." >&2
  echo "Install ffmpeg and ffprobe another way, then point MEDIA_LAB_FFMPEG_DIR at them." >&2
  exit 1
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin_dir="$root/bin"
mkdir -p "$bin_dir"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

fetch() {
  local name="$1" url="$2" want="$3"
  echo "==> $name"
  curl -fsSL -o "$tmp/$name.zip" "$url"
  unzip -o -q "$tmp/$name.zip" -d "$tmp/$name"
  local got
  got="$(shasum -a 256 "$tmp/$name/$name" | cut -d' ' -f1)"
  if [[ "$got" != "$want" ]]; then
    echo "error: $name checksum mismatch." >&2
    echo "  expected $want" >&2
    echo "  got      $got" >&2
    exit 1
  fi
  install -m 0755 "$tmp/$name/$name" "$bin_dir/$name"
  xattr -d com.apple.quarantine "$bin_dir/$name" 2>/dev/null || true
  "$bin_dir/$name" -version | head -1
}

fetch ffmpeg "$FFMPEG_URL" "$FFMPEG_SHA256"
fetch ffprobe "$FFPROBE_URL" "$FFPROBE_SHA256"
echo "done: $bin_dir"
