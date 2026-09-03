"""Put an audio track back onto a video that lost it.

Compositing renders video only, so the original voice has to be re-attached
before a music bed can be ducked under it.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..errors import ValidationError
from ..ffmpeg import run_ffmpeg
from ..paths import ensure_readable_source, ensure_writable_output
from ..probe import MediaInfo, probe
from ..verify import Expectations, verify_render

AUDIO_CODEC = "aac"
AUDIO_BITRATE = "192k"


def attach_audio(
    video: Path | str,
    audio_source: Path | str,
    output: Path | str,
    config: Config,
    *,
    force: bool = False,
) -> MediaInfo:
    """Copy the video stream from one file and the audio stream from another."""
    resolved_video = ensure_readable_source(video)
    resolved_audio = ensure_readable_source(audio_source)
    resolved_output = ensure_writable_output(output, config, force=force)

    video_info = probe(resolved_video, config)
    audio_info = probe(resolved_audio, config)
    if not video_info.has_video:
        raise ValidationError(f"no video stream to keep in {resolved_video}")
    if not audio_info.has_audio:
        raise ValidationError(f"no audio stream to take from {resolved_audio}")

    # The video stream is copied, not re-encoded: every file this is used on
    # comes from an earlier stage of our own pipeline and is already H.264 in
    # MP4. ffmpeg fails loudly if a future stage produces something the
    # container cannot hold, and verify_render catches a missing output.
    run_ffmpeg(
        [
            "-i",
            str(resolved_video),
            "-i",
            str(resolved_audio),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            AUDIO_CODEC,
            "-b:a",
            AUDIO_BITRATE,
            "-t",
            f"{video_info.duration_s:.3f}",
            str(resolved_output),
        ],
        config,
    )
    return verify_render(
        resolved_output,
        config,
        Expectations(duration_s=video_info.duration_s, requires_audio=True),
    )
