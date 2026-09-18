# Voice Memos Studio Renderer

A small macOS command-line tool that renders Apple's **Studio Voice** processing from compatible Voice Memos spatial recordings and writes the result as **Apple Lossless (ALAC)**.

The project came out of reverse-engineering how the macOS Voice Memos app stores and renders Studio Voice. The working renderer itself does **not** patch Voice Memos, attach a debugger to it, or modify its database. It uses Apple system frameworks to build the Studio Voice audio mix, renders that mix to PCM, then writes ALAC.

## What it does

```text
Voice Memos .qta
      │
      ▼
CNAssetSpatialAudioInfo
      │
      ▼
Studio Voice audio mix
(effectIntensity 0.0 ... 1.0)
      │
      ▼
48 kHz / stereo / 32-bit float PCM
      │
      ▼
Apple Lossless (ALAC) .m4a
```

Tested output:

- codec: ALAC
- sample rate: 48 kHz
- channels: stereo
- decoded sample format reported by ffprobe: `s32p`
- `bits_per_raw_sample=32`

## Requirements

- macOS with the Apple frameworks used by the tool
- Xcode Command Line Tools / Swift compiler
- a compatible Voice Memos spatial `.qta` recording

The implementation was tested on macOS 27.0. Older macOS releases are currently untested.

## Build

```bash
make
```

Equivalent command:

```bash
xcrun swiftc \
  -parse-as-library \
  vm-studio-lossless.swift \
  -framework AVFoundation \
  -framework Cinematic \
  -framework AudioToolbox \
  -o vm-studio-lossless
```

## Usage

```bash
./vm-studio-lossless <input.qta> <output.m4a> <intensity>
```

`intensity` must be between `0.0` and `1.0`.

Example:

```bash
./vm-studio-lossless \
  "recording.qta" \
  "recording-studio.m4a" \
  0.25
```

For a Voice Memo whose Studio Voice slider is stored as 25%, use `0.25`.

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

## Why ALAC?

A first proof-of-concept path successfully rendered Studio Voice but produced AAC. This version instead asks AVFoundation for rendered PCM and sends that PCM to an `AVAssetWriter` configured for Apple Lossless.

That does **not** make the original recording magically lossless. If the source audio was already compressed, that information is already gone. ALAC simply avoids another lossy encode after Studio Voice processing.

## Important limitations

- Only recordings compatible with `CNAssetSpatialAudioInfo` are expected to work.
- Apple can change Voice Memos internals or system-framework behavior in future macOS releases.
- The `.qta` container is an Apple implementation detail and should not be treated as a stable public interchange format.
- The tool currently forces output to 48 kHz, stereo, 32-bit floating-point PCM before ALAC encoding.
- Several AVAssetReader/Writer APIs used by this proof-of-concept are deprecated in the macOS 27 SDK. They still worked in testing, but a future version should migrate to the newer provider/receiver APIs.

## Reverse-engineering notes

See [docs/reverse-engineering.md](docs/reverse-engineering.md) for the evidence trail and [docs/validation.md](docs/validation.md) for the measured output from the working prototype.

## Legal / project status

This is an independent interoperability and research project. It is not affiliated with or endorsed by Apple.

No Apple binaries, private framework files, recordings, or Voice Memos databases are included in this repository.

## License

MIT. See [LICENSE](LICENSE).
