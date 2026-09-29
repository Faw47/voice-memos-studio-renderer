#!/usr/bin/env python3
"""Fail-closed export checks and atomic publication without replacement."""
import json
import math
import os
import subprocess
import sys


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    if result.returncode:
        raise ValueError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def duration(info):
    value = float(info["format"]["duration"])
    if not math.isfinite(value) or value <= 0:
        raise ValueError("missing, nonfinite, or empty audio duration")
    return value


def verify(source, output, mode):
    if mode not in ("lossless", "opus"):
        raise ValueError(f"unknown export mode: {mode}")
    original, rendered = probe(source), probe(output)
    source_duration, output_duration = duration(original), duration(rendered)
    # One second permits container/codec padding, but never scales with lecture length.
    if abs(source_duration - output_duration) > 1.0:
        raise ValueError(
            f"duration mismatch: source={source_duration:.6f}s output={output_duration:.6f}s"
        )
    streams = rendered["streams"]
    if len(streams) != 1 or streams[0].get("codec_type") != "audio":
        raise ValueError("expected exactly one audio stream and no other streams")
    audio = streams[0]
    expected = ("alac", "48000", 2) if mode == "lossless" else ("opus", "48000", 1)
    actual = (audio.get("codec_name"), audio.get("sample_rate"), audio.get("channels"))
    if actual != expected:
        raise ValueError(f"unexpected audio format: {actual}, expected {expected}")
    container = rendered["format"].get("format_name", "").split(",")
    if mode == "lossless":
        if "m4a" not in container or int(audio.get("bits_per_raw_sample", 0)) != 32:
            raise ValueError("expected 32-bit ALAC in M4A")
    elif "ogg" not in container:
        raise ValueError("expected Ogg container")
    if os.path.getsize(output) <= 0:
        raise ValueError("empty output file")
    print(f"Verified {mode}: {output_duration:.6f}s, codec={actual[0]}, rate={actual[1]}, channels={actual[2]}")


def main():
    action, *args = sys.argv[1:]
    if action == "preflight":
        source, output, intensity_text = args
        intensity = float(intensity_text)
        if not math.isfinite(intensity) or not 0 <= intensity <= 1:
            raise ValueError("intensity must be finite and between 0 and 1")
        if os.path.realpath(source) == os.path.realpath(output) or os.path.lexists(output):
            raise ValueError("destination exists or aliases the source")
        duration(probe(os.path.abspath(source)))
    elif action == "verify":
        verify(*args)
    elif action == "publish":
        staged, output = args
        # Flush file data before publishing. link() atomically fails for ANY existing
        # destination, including a file, directory, symlink, or a concurrent export.
        with open(staged, "rb") as handle:
            os.fsync(handle.fileno())
        os.link(staged, output)
    else:
        raise ValueError(f"unknown action: {action}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
