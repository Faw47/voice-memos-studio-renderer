# Voice Memos Studio Renderer

A macOS command-line tool that renders Apple's **Studio Voice** processing from compatible Voice Memos spatial recordings.

The normal output is a compact, transcription-friendly **Ogg Opus** file:

- Opus
- Ogg container
- mono
- 48 kHz
- 64 kbps VBR

A lossless ALAC/M4A render remains available with `--lossless`.

The project came out of reverse-engineering how the macOS Voice Memos app stores and renders Studio Voice. It does **not** patch Voice Memos, attach a debugger to it, or modify its database.

## Pipeline

```text
Voice Memos .qta
      │
      ▼
CNAssetSpatialAudioInfo
      │
      ▼
defaultSpatialAudioTrack
      │
      ▼
Studio Voice audio mix
(effectIntensity 0.0 ... 1.0)
      │
      ▼
Apple stereo PCM render
      │
      ├──────── --lossless ───────► ALAC / M4A
      │
      ▼
mono / 48 kHz
      │
      ▼
Opus 64 kbps VBR / Ogg
```

## Requirements

- macOS with the Apple frameworks used by the tool
- Xcode Command Line Tools / Swift compiler
- `ffmpeg` and `ffprobe` for the normal Opus workflow
- a compatible Voice Memos spatial `.qta` recording

The implementation was tested on macOS 27.0. Older macOS releases are currently untested.

## Build

```bash
make
```

This builds the Apple/AVFoundation renderer as:

```text
vm-studio-lossless
```

and makes the normal wrapper executable:

```text
vm-studio
```

## Usage

### Default: compact Ogg Opus

```bash
./vm-studio \
  "recording.qta" \
  "recording-studio.ogg" \
  0.25
```

Output profile:

```text
container:    Ogg
codec:        Opus
sample rate:  48 kHz
channels:     mono
bitrate:      64 kbps VBR
application:  audio
```

The wrapper first renders Studio Voice through Apple's spatial-audio path at full quality, then converts that processed result to Opus. Downmixing and compression happen **after** Studio Voice processing.

It verifies that the result is Opus / 48 kHz / mono and performs a full decode test before replacing the requested destination.

### Optional lossless render

```bash
./vm-studio --lossless \
  "recording.qta" \
  "recording-studio.m4a" \
  0.25
```

This preserves the previous ALAC/M4A output path.

## Why Opus by default?

The original 48 kHz stereo 32-bit ALAC renders were unnecessarily large for lecture and transcription workflows.

In a 13-file lecture batch, converting the rendered files to the default Opus profile reduced total size from:

```text
6466.40 MB
```

to:

```text
214.82 MB
```

for a **96.68% reduction**, while every output:

- decoded successfully end-to-end
- reported Opus / 48 kHz / mono
- stayed within 0.063 seconds of its source duration

The compact Opus files are intended for transcription, normal playback, and long-term lecture storage. Use `--lossless` when a lossless post-effect master is specifically required.

## Correct spatial-track export path

The renderer follows `CNAssetSpatialAudioInfo`'s export contract: it reads only `defaultSpatialAudioTrack` and uses `assetReaderOutputSettings(for: .stereo)` when constructing `AVAssetReaderAudioMixOutput`.

An earlier revision passed every audio track in the asset to the mix output. Spatial Voice Memo containers can carry multiple audio representations, which caused duplicate speech with a fixed delay in affected exports. Those older exports should not be treated as validated masters.

## Finding Voice Memos recordings

On current macOS builds, local Voice Memos assets are commonly stored under:

```text
~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/
```

Spatial recordings may use the `.qta` extension.

The Voice Memos database in the same area can contain fields such as:

- `ZSTUDIOMIXENABLED`
- `ZSTUDIOMIXLEVEL`
- `ZUNIQUEID`
- `ZPATH`

This project does **not** require modifying that database.

## Validation before deleting a source

Do not treat codec, duration, or decode success alone as proof that an export is correct.

Before deleting a Voice Memo source:

1. confirm the output exists;
2. confirm the expected codec/rate/channel layout;
3. perform a full decode test;
4. confirm duration is plausible;
5. spot-listen to beginning, middle, and end;
6. specifically check for delayed duplicate speech or other content-level defects.

## Important limitations

- Only recordings compatible with `CNAssetSpatialAudioInfo` are expected to work.
- Apple can change Voice Memos internals or system-framework behavior in future macOS releases.
- The `.qta` container is an Apple implementation detail and should not be treated as a stable public interchange format.
- The default Opus path is lossy. Use `--lossless` when a lossless post-effect render is required.
- The default wrapper temporarily creates a lossless render before encoding Opus, then deletes the temporary file.
- The modern branch uses the newer AVFoundation provider/receiver APIs.

## Reverse-engineering notes

See [docs/reverse-engineering.md](docs/reverse-engineering.md) for the evidence trail and [docs/validation.md](docs/validation.md) for validation history.

## Legal / project status

This is an independent interoperability and research project. It is not affiliated with or endorsed by Apple.

No Apple binaries, private framework files, recordings, or Voice Memos databases are included in this repository.

## License

MIT. See [LICENSE](LICENSE).
