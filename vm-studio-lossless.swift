import Foundation
import AVFoundation
import Cinematic
import AudioToolbox
import Darwin

enum RenderError: Error, CustomStringConvertible {
    case usage
    case noAudioTracks
    case cannotAddReaderOutput
    case cannotAddWriterInput
    case readerStartFailed(String)
    case writerStartFailed(String)
    case appendFailed(String)
    case readerFailed(String)
    case writerFailed(String)

    var description: String {
        switch self {
        case .usage:
            return "usage: vm-studio-lossless <input.qta> <output.m4a> <intensity 0...1>"
        case .noAudioTracks:
            return "No audio tracks found"
        case .cannotAddReaderOutput:
            return "Could not add AVAssetReaderAudioMixOutput"
        case .cannotAddWriterInput:
            return "Could not add AVAssetWriterInput"
        case .readerStartFailed(let s):
            return "Reader failed to start: \(s)"
        case .writerStartFailed(let s):
            return "Writer failed to start: \(s)"
        case .appendFailed(let s):
            return "Writer append failed: \(s)"
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

            let audioTracks = try await asset.loadTracks(withMediaType: .audio)
            guard !audioTracks.isEmpty else {
                throw RenderError.noAudioTracks
            }

            // Apple's Spatial Audio / Studio Voice processing.
            let spatialInfo = try await CNAssetSpatialAudioInfo(asset: asset)

            let audioMix = spatialInfo.audioMix(
                effectIntensity: intensity,
                renderingStyle: .studio
            )

            // Decode + render the Audio Mix into uncompressed 48 kHz,
            // stereo, 32-bit floating-point PCM.
            let reader = try AVAssetReader(asset: asset)

            let pcmSettings: [String: Any] = [
                AVFormatIDKey: kAudioFormatLinearPCM,
                AVSampleRateKey: 48_000,
                AVNumberOfChannelsKey: 2,
                AVLinearPCMBitDepthKey: 32,
                AVLinearPCMIsFloatKey: true,
                AVLinearPCMIsBigEndianKey: false,
                AVLinearPCMIsNonInterleaved: false
            ]

            let mixOutput = AVAssetReaderAudioMixOutput(
                audioTracks: audioTracks,
                audioSettings: pcmSettings
            )

            mixOutput.audioMix = audioMix
            mixOutput.alwaysCopiesSampleData = false

            guard reader.canAdd(mixOutput) else {
                throw RenderError.cannotAddReaderOutput
            }

            reader.add(mixOutput)

            // Encode that rendered PCM to Apple Lossless.
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

            writerInput.expectsMediaDataInRealTime = false

            guard writer.canAdd(writerInput) else {
                throw RenderError.cannotAddWriterInput
            }

            writer.add(writerInput)

            guard writer.startWriting() else {
                throw RenderError.writerStartFailed(
                    writer.error?.localizedDescription ?? "unknown error"
                )
            }

            writer.startSession(atSourceTime: .zero)

            guard reader.startReading() else {
                throw RenderError.readerStartFailed(
                    reader.error?.localizedDescription ?? "unknown error"
                )
            }

            var sampleCount: UInt64 = 0

            while reader.status == .reading {
                if writerInput.isReadyForMoreMediaData {
                    if let sampleBuffer = mixOutput.copyNextSampleBuffer() {
                        if !writerInput.append(sampleBuffer) {
                            throw RenderError.appendFailed(
                                writer.error?.localizedDescription ?? "unknown error"
                            )
                        }

                        sampleCount += 1

                        if sampleCount % 500 == 0 {
                            let pts = CMSampleBufferGetPresentationTimeStamp(sampleBuffer)
                            let seconds = CMTimeGetSeconds(pts)

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
                    } else {
                        break
                    }
                } else {
                    usleep(10_000)
                }
            }

            if reader.status == .failed {
                throw RenderError.readerFailed(
                    reader.error?.localizedDescription ?? "unknown error"
                )
            }

            writerInput.markAsFinished()

            await withCheckedContinuation { continuation in
                writer.finishWriting {
                    continuation.resume()
                }
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
