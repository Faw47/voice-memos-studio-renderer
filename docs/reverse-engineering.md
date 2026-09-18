# Reverse-engineering notes

This document separates **observed facts** from **inferences** made while investigating Studio Voice in Voice Memos.

## 1. Studio Voice state is stored separately from the source asset

Inspection of `CloudRecordings.db` showed Studio Voice-related fields on recording rows, including:

```text
ZSTUDIOMIXENABLED
ZSTUDIOMIXLEVEL
```

A spatial Voice Memo with Studio Voice enabled showed values equivalent to:

```text
ZSTUDIOMIXENABLED = 1
ZSTUDIOMIXLEVEL   = 0.25
```

Changing the Studio Voice slider in Voice Memos changed the database value, while the source `.qta` file's SHA-256 and Voice Memos audio-flags extended attribute stayed unchanged.

### Conclusion

For the tested recording, Studio Voice intensity was **non-destructive state** rather than audio already baked into the `.qta` file.

Copying the `.qta` file alone therefore preserves the source asset but does not itself bake the selected Studio Voice intensity into a conventional exported audio file.

## 2. Voice Memos contains an offline effect-rendering path

Static inspection of the macOS Voice Memos executable exposed Swift/Objective-C runtime names and selectors including:

```text
ComposedAudioEffectRenderer
EffectsRendererSettingsProvider
EffectRendererInfoProviding
renderRecordingWithId:intoDirectory:with:completionHandler:
rendererSettingsFromRecordingWithId:completionHandler:
renderOffline:toBuffer:error:
studioVoiceInputParameters(effectIntensity:volume:)
spatialAudioMix(trackVolumes:studioVoiceValue:)
```

These names strongly indicated that Voice Memos constructs an audio mix for Studio Voice and can render the result offline.

They were clues, not a callable public API contract for this project.

## 3. Related spatial-export machinery exists elsewhere in Voice Memos

Inspection of Voice Memos-related code also exposed names such as:

```text
RCSpatialExporter
RCExportSessionComposedAssetWriter
AVAssetExportPresetVoiceMemoALAC
compositionAssetForExport:
hasSpatialAudio
rc_hasSpatialTracks
```

Important distinction: the presence of those names does **not** by itself prove that a particular Finder drag, Share action, or Studio Voice export uses that exact path or preset.

We treated these as reverse-engineering clues only.

## 4. The key usable system-framework API

The working standalone renderer uses:

```swift
let spatialInfo = try await CNAssetSpatialAudioInfo(asset: asset)

let audioMix = spatialInfo.audioMix(
    effectIntensity: intensity,
    renderingStyle: .studio
)
```

That audio mix is attached to an `AVAssetReaderAudioMixOutput`.

The reader therefore returns PCM after Apple's Studio Voice processing has been applied.

## 5. Why the renderer does not attach to Voice Memos

Attaching LLDB to the system Voice Memos process was denied by macOS process protections.

That turned out not to be necessary. Once the spatial-audio mix path was identified, the effect could be rendered from a separate Swift executable.

The current repository therefore does not:

- inject code into Voice Memos
- disable SIP
- modify Apple binaries
- patch private frameworks
- require debugger attachment

## 6. Database identifiers

The recording table also exposed identifiers such as:

```text
ZPATH
ZUNIQUEID
ZAUDIOFUTUREUUIDS
```

Those helped map database rows to source assets while investigating the app.

The standalone renderer does not need a Voice Memos UUID. It operates directly on the input asset URL.

## 7. What remains uncertain

The following should be treated as implementation details, not guaranteed behavior:

- whether Apple will continue using `.qta` for these recordings
- whether database column names remain stable
- whether Studio Voice continues to map to the same system-framework behavior
- which exact internal exporter Voice Memos uses for every user-facing share/export route
- whether older macOS versions provide the same APIs and rendering results

Those uncertainties are why the repository keeps the renderer itself small and avoids depending on the Voice Memos database.
