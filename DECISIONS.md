# DECISIONS.md

Technical decisions taken on this project, with the trade-off each one accepts.
Newest first.

---

## 2026-09-03 — Wrap Kinocut rather than write our own ffmpeg layer

**Context.** The goal was a local editor for short social clips: person
cutout, new backdrop, looks, background music, vertical export. A GitHub survey
turned up ~20 "ffmpeg MCP" projects, nearly all at 0-3 stars and unmaintained.
`KyaniteLabs/kinocut` (136 stars, Apache-2.0, active) was the only serious
candidate, and it is built on the same principle we wanted: typed tools with
preflight validation instead of agent-invented ffmpeg flags.

**Chosen.** Build a typed Python wrapper over kinocut's `kino` CLI, with our own
configuration, path safety and render verification on top.

**Trade-off accepted.** kinocut has a bus factor of one (1208 of its commits are
from a single author) and is ~6 months old, so its API may move. We pin
`kinocut==1.15.1` and keep every call behind `kino.py`, so a breaking change hits
one module rather than the whole codebase.

---

## 2026-09-03 — Drive kinocut through its CLI, not its MCP server

**Context.** kinocut exposes 196 MCP tools and 167 CLI commands over the same
engine.

**Chosen.** The CLI, invoked as a subprocess from `kino.py`.

**Trade-off accepted.** MCP would validate parameters before execution; the CLI
does not, so we validate in our own recipes. In exchange, tool definitions cost
no context on every message, output is trivially testable, and the same calls
work from code and from the shell.

---

## 2026-09-03 — Static ffmpeg in `bin/` instead of Homebrew

**Context.** ffmpeg is mandatory; the machine had neither ffmpeg nor Homebrew.

**Chosen.** Download pinned arm64 binaries into `./bin` via
`scripts/fetch-ffmpeg.sh`, with SHA256 verification.

**Trade-off accepted.** Updates are manual and the binaries are macOS arm64 only,
so the project is not portable as-is. In exchange nothing is installed globally,
the ffmpeg version is pinned and reproducible, and setup does not depend on a
package manager. Note that evermeet.cx, the best-known macOS source, ships
x86_64 builds that would have run under Rosetta; the arm64 builds come from
osxexperts.net.

---

## 2026-09-03 — Build the music bed with ffmpeg, not `kino audio-bed`

**Context.** `kino audio-bed` does exactly what we need — sidechain ducking plus
EBU R128 normalisation in one pass — but it cannot run on macOS. kinocut 1.15.1
gates it behind immutable source snapshots built on `os.memfd_create`, a
Linux-only API, and it fails with `source_identity_changed` before touching any
media. Verified directly: `hasattr(os, "memfd_create")` is `False` on Darwin.
Only `audio-bed` and `body-swap` depend on it.

**Chosen.** Implement ducking in `recipes/audio_bed.py` with ffmpeg's own
`sidechaincompress` and `loudnorm`, through a new `ffmpeg.py` module.

**Trade-off accepted.** One recipe no longer goes through kinocut, so the
"everything behind `kino.py`" rule now has a second sanctioned exit through
`ffmpeg.py`. The alternative — `kino add-audio --mix` — works but does no
ducking, which was the point. Measured result: -16.04 LUFS against a -16.0
target.

---

## 2026-09-03 — Write cutouts as ProRes 4444 `.mov`, not VP9 WebM

**Context.** `hyperframes-remove-background` defaults to WebM. That file really
does carry alpha, but only ffmpeg's `libvpx-vp9` decoder exposes it, and
kinocut's compositor does not request that decoder. The result composited the
subject as an opaque rectangle over the backdrop — a wrong result that looked
entirely plausible and that probing could not distinguish from a correct one.

**Chosen.** Ask for `.mov`, which the tool renders as ProRes 4444
(`yuva444p12le`); ffmpeg reads that alpha natively.

**Trade-off accepted.** ProRes is very large — 214 MB for 6.4 seconds — so
`work/` grows quickly and the test suite got noticeably slower. Correctness over
disk.

---

## 2026-09-03 — Clamp the compositor canvas to 25 fps

**Context.** kinocut's compositor renders at most 25 fps but tags the output
with whatever fps the canvas asked for. Measured across durations and rates:
a request for `duration x fps` frames always yields `duration x min(fps, 25)`.
A 30 fps source therefore came out 5.37s instead of 6.43s.

**Chosen.** `backdrop.py` clamps the canvas fps to 25 and reports the clamp.

**Trade-off accepted.** Composited output moves at 25 fps rather than the
source's frame rate. Running time and audio sync stay correct, which matters
more for short social clips than the extra 5 fps.

---

## 2026-09-03 — Verify that alpha varies, not merely that it exists

**Context.** The first alpha check only asked whether a file had an alpha
channel. A matte that is uniformly opaque separates nothing, yet produces a
file that passes that check.

**Chosen.** `ffmpeg.measure_alpha_spread` measures the actual min/max of the
alpha plane on one frame; `cutout` fails the render when the spread is zero.

**Trade-off accepted.** One extra ffmpeg pass per cutout. Worth it: this is the
failure mode that is hardest to notice by eye.
