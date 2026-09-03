"""Mix a music bed under the voice, with automatic sidechain ducking.

kinocut exposes `audio-bed` for exactly this, but that command cannot run on
macOS: kinocut 1.15.1 gates it behind immutable source snapshots built on
os.memfd_create, which is Linux-only, so it fails closed with
`source_identity_changed` before touching any media. The filtergraph below
does the same job — duck, mix, normalise — through ffmpeg directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..errors import ValidationError
from ..ffmpeg import measure_integrated_loudness, run_ffmpeg
from ..paths import ensure_readable_source, ensure_writable_output
from ..probe import MediaInfo, probe
from ..validation import check_range
from ..verify import Expectations, verify_render

MIN_TARGET_LUFS = -70.0
MAX_TARGET_LUFS = -5.0
MIN_MUSIC_VOLUME = 0.0
MAX_MUSIC_VOLUME = 2.0
MIN_DUCK_RATIO = 1.0
MAX_DUCK_RATIO = 20.0
MIN_DUCK_THRESHOLD = 0.0
MAX_DUCK_THRESHOLD = 1.0
MIN_DUCK_TIME_MS = 0.01
MAX_DUCK_ATTACK_MS = 2000.0
MAX_DUCK_RELEASE_MS = 9000.0

DEFAULT_TARGET_LUFS = -16.0
DEFAULT_MUSIC_VOLUME = 1.0
DEFAULT_DUCK_THRESHOLD = 0.02
DEFAULT_DUCK_RATIO = 5.0
DEFAULT_DUCK_ATTACK_MS = 25.0
DEFAULT_DUCK_RELEASE_MS = 450.0

TRUE_PEAK_CEILING_DB = -1.5
LOUDNESS_RANGE = 11.0
AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"


@dataclass(frozen=True, slots=True)
class AudioBedResult:
    """The mixed render, plus the loudness actually measured on the output."""

    media: MediaInfo
    measured_lufs: float
    ducking_engaged: bool


def _duck_filtergraph(
    music_volume: float,
    target_lufs: float,
    duck_threshold: float,
    duck_ratio: float,
    duck_attack_ms: float,
    duck_release_ms: float,
) -> str:
    """Music is compressed by the voice, then the two are mixed and normalised."""
    return (
        f"[1:a]volume={music_volume}[bed];"
        f"[bed][0:a]sidechaincompress="
        f"threshold={duck_threshold}:ratio={duck_ratio}"
        f":attack={duck_attack_ms}:release={duck_release_ms}[ducked];"
        f"[0:a][ducked]amix=inputs=2:duration=first:normalize=0[mixed];"
        f"[mixed]loudnorm=I={target_lufs}:TP={TRUE_PEAK_CEILING_DB}:LRA={LOUDNESS_RANGE}[out]"
    )


def _music_only_filtergraph(music_volume: float, target_lufs: float) -> str:
    """With no voice to duck against, the bed simply becomes the track."""
    return (
        f"[1:a]volume={music_volume}[bed];"
        f"[bed]loudnorm=I={target_lufs}:TP={TRUE_PEAK_CEILING_DB}:LRA={LOUDNESS_RANGE}[out]"
    )


def add_music_bed(
    source: Path | str,
    music: Path | str,
    output: Path | str,
    config: Config,
    *,
    target_lufs: float = DEFAULT_TARGET_LUFS,
    music_volume: float = DEFAULT_MUSIC_VOLUME,
    loop: bool = True,
    duck_threshold: float = DEFAULT_DUCK_THRESHOLD,
    duck_ratio: float = DEFAULT_DUCK_RATIO,
    duck_attack_ms: float = DEFAULT_DUCK_ATTACK_MS,
    duck_release_ms: float = DEFAULT_DUCK_RELEASE_MS,
    force: bool = False,
) -> AudioBedResult:
    """Place a music bed under a clip, ducking it whenever the voice speaks."""
    resolved_source = ensure_readable_source(source)
    resolved_music = ensure_readable_source(music)
    resolved_output = ensure_writable_output(output, config, force=force)
    check_range(target_lufs, MIN_TARGET_LUFS, MAX_TARGET_LUFS, "target_lufs")
    check_range(music_volume, MIN_MUSIC_VOLUME, MAX_MUSIC_VOLUME, "music_volume")
    check_range(duck_ratio, MIN_DUCK_RATIO, MAX_DUCK_RATIO, "duck_ratio")
    # These are interpolated into an ffmpeg filtergraph, so they are bounded
    # here rather than passed through as free-form text.
    check_range(duck_threshold, MIN_DUCK_THRESHOLD, MAX_DUCK_THRESHOLD, "duck_threshold")
    check_range(duck_attack_ms, MIN_DUCK_TIME_MS, MAX_DUCK_ATTACK_MS, "duck_attack_ms")
    check_range(duck_release_ms, MIN_DUCK_TIME_MS, MAX_DUCK_RELEASE_MS, "duck_release_ms")

    source_info = probe(resolved_source, config)
    if source_info.duration_s <= 0:
        raise ValidationError(f"source has no measurable duration: {resolved_source}")
    music_info = probe(resolved_music, config)
    if not music_info.has_audio:
        raise ValidationError(f"music file has no audio stream: {resolved_music}")

    ducking_engaged = source_info.has_audio
    filtergraph = (
        _duck_filtergraph(
            music_volume, target_lufs, duck_threshold, duck_ratio, duck_attack_ms, duck_release_ms
        )
        if ducking_engaged
        else _music_only_filtergraph(music_volume, target_lufs)
    )

    args = ["-i", str(resolved_source)]
    if loop:
        args += ["-stream_loop", "-1"]
    args += ["-i", str(resolved_music), "-filter_complex", filtergraph]
    if source_info.has_video:
        args += ["-map", "0:v", "-c:v", "copy"]
    args += [
        "-map",
        "[out]",
        "-c:a",
        AUDIO_CODEC,
        "-b:a",
        AUDIO_BITRATE,
        "-t",
        f"{source_info.duration_s:.3f}",
        str(resolved_output),
    ]
    run_ffmpeg(args, config)

    media = verify_render(
        resolved_output,
        config,
        Expectations(
            duration_s=source_info.duration_s,
            requires_video=source_info.has_video,
            requires_audio=True,
        ),
    )
    return AudioBedResult(
        media=media,
        measured_lufs=measure_integrated_loudness(resolved_output, config),
        ducking_engaged=ducking_engaged,
    )
