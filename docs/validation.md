# Validation

These are measurements from the working proof-of-concept used to validate the renderer.

## Test source

A spatial Voice Memos `.qta` recording approximately 56 minutes 55 seconds long was used.

The recording had Studio Voice enabled, with the Voice Memos database storing an intensity of `0.25`.

No personal recording title, path UUID, or database contents are included here.

## Test 1: source asset does not change with the slider

The Studio Voice intensity was changed in Voice Memos.

Observed:

- the database Studio Voice level changed
- the source `.qta` SHA-256 did not change
- the tested Voice Memos audio-flags xattr did not change

This supports the conclusion that the slider value is external/non-destructive state for the tested asset.

## Test 2: first rendered proof of concept

An earlier rendering path produced:

```text
codec_name=aac
sample_rate=48000
channels=2
channel_layout=stereo
bit_rate=143515

duration=3415.253333
size=61923035
format_bit_rate=145050
```

That established that the Studio Voice mix could be rendered, but the output still introduced a lossy AAC encode.

## Test 3: explicit PCM render + ALAC writer

The implementation in this repository renders the audio mix to PCM and then writes Apple Lossless.

Observed with `ffprobe`:

```text
codec_name=alac
codec_long_name=ALAC (Apple Lossless Audio Codec)
sample_fmt=s32p
sample_rate=48000
channels=2
channel_layout=stereo
bit_rate=2009219
bits_per_raw_sample=32

duration=3415.296000
size=857935626
format_bit_rate=2009631
```

### Result

The final file is an ALAC `.m4a` rather than AAC.

This means the post-effect render is not subjected to another lossy codec stage.

It does **not** imply that the original Voice Memo source was lossless.

## Reproducing the inspection

```bash
ffprobe -hide_banner -v error \
  -show_entries \
stream=codec_name,codec_long_name,sample_fmt,sample_rate,channels,channel_layout,bits_per_raw_sample,bit_rate \
  -show_entries format=format_name,duration,size,bit_rate \
  -of default=noprint_wrappers=1 \
  output.m4a
```

## Suggested A/B validation

For a compatible source, render the same file at two intensities:

```bash
./vm-studio-lossless input.qta studio-0.m4a 0
./vm-studio-lossless input.qta studio-25.m4a 0.25
```

Then compare or null-test the decoded audio. This is useful when validating behavior on a different macOS release.
