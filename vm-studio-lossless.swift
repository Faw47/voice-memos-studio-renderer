import Foundation
import AVFoundation
import Cinematic
import AudioToolbox
import Darwin

enum RenderError: Error, CustomStringConvertible {
    case usage
    case cannotAddReaderOutput
    case cannotAddWriterInput
    case readerFailed(String)
    case writerFailed(String)

    var description: String {
        switch self {
        case .usage:
            return "usage: vm-studio-lossless <input.qta> <output.m4a> <intensity 0...1>"
        case .cannotAddReaderOutput:
            return "Could not attach AVAssetReaderAudioMixOutput"
        case .cannotAddWriterInput:
            return "Could not attach AVAssetWriterInput"
        case .readerFailed(let s):
            return "Reader failed: \(s)"
        case .writerFailed(let s):
            return "Writer failed: \(s)"
        }
    }
}

@main
struct VMStudioLossless {
    static func main() async {
        do {
            guard CommandLine.arguments.count == 4 else {
                throw RenderError.usage
            }

            let sourceURL = URL(fileURLWithPath: CommandLine.arguments[1])
            let destinationURL = URL(fileURLWithPath: CommandLine.arguments[2])

            guard let intensity = Float(CommandLine.arguments[3]),
                  intensity >= 0,
                  intensity <= 1 else {
                throw RenderError.usage
            }

            try? FileManager.default.removeItem(at: destinationURL)

            let asset = AVURLAsset(url: sourceURL)

            // Apple's Spatial Audio / Studio Voice processing.
            let spatialInfo = try await CNAssetSpatialAudioInfo(asset: asset)

            let audioMix = spatialInfo.audioMix(
                effectIntensity: intensity,
                renderingStyle: .studio
            )

            // CNAssetSpatialAudioInfo's export contract is specific:
            // use the default Spatial Audio track and the reader settings
            // supplied for the requested output content type. Passing every
            // audio track in the asset can mix alternate representations of
            // the same recording together and produce delayed duplicate audio.
            let spatialTrack = spatialInfo.defaultSpatialAudioTrack
            let pcmSettings = spatialInfo.assetReaderOutputSettings(for: .stereo)

            // Decode + render Apple's Audio Mix to stereo LPCM.
            let reader = try AVAssetReader(asset: asset)

            let mixOutput = AVAssetReaderAudioMixOutput(
                audioTracks: [spatialTrack],
                audioSettings: pcmSettings
            )

            mixOutput.audioMix = audioMix

            guard reader.canAdd(mixOutput) else {
                throw RenderError.cannotAddReaderOutput
            }

            // macOS 27 replacement for reader.add(...) +
            // mixOutput.copyNextSampleBuffer().
            let outputProvider = reader.outputProvider(for: mixOutput)

            // Encode the rendered PCM to Apple Lossless.
            let writer = try AVAssetWriter(
                outputURL: destinationURL,
                fileType: .m4a
            )

            let alacSettings: [String: Any] = [
                AVFormatIDKey: kAudioFormatAppleLossless,
                AVSampleRateKey: 48_000,
                AVNumberOfChannelsKey: 2,
                AVEncoderBitDepthHintKey: 32
            ]

            let writerInput = AVAssetWriterInput(
                mediaType: .audio,
                outputSettings: alacSettings
            )

            guard writer.canAdd(writerInput) else {
                throw RenderError.cannotAddWriterInput
            }

            // macOS 27 replacement for writer.add(...) +
            // writerInput.append(...).
            let sampleReceiver = writer.inputReceiver(for: writerInput)

            try writer.start()
            writer.startSession(atSourceTime: .zero)
            try reader.start()

            var sampleCount: UInt64 = 0

            while let sampleBuffer = try await outputProvider.next() {
                sampleCount += 1

                if sampleCount % 500 == 0 {
                    let seconds = CMTimeGetSeconds(sampleBuffer.presentationTimeStamp)

                    if seconds.isFinite {
                        fputs(
                            String(
                                format: "\rRendered %.1f minutes",
                                seconds / 60.0
                            ),
                            stderr
                        )
                        fflush(stderr)
                    }
                }

                // Suspends until the writer is ready, then appends.
                try await sampleReceiver.append(sampleBuffer)
            }

            sampleReceiver.finish()
            await writer.finishWriting()

            if reader.status == .failed {
                throw RenderError.readerFailed(
                    reader.error?.localizedDescription ?? "unknown error"
                )
            }

            guard writer.status == .completed else {
                throw RenderError.writerFailed(
                    writer.error?.localizedDescription ?? "unknown error"
                )
            }

            fputs("\n", stderr)
            print("Rendered losslessly:")
            print(destinationURL.path)

        } catch {
            fputs("ERROR: \(error)\n", stderr)
            exit(1)
        }
    }
}
