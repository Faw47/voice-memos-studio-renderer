"""Real FFmpeg tests; the Apple renderer is replaced by a controlled ALAC fixture.

These validate the wrapper, not Studio Voice's perceptual quality or Apple APIs.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


class WrapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.fixture_dir.name) / "fixture.m4a"
        subprocess.run([
            FFMPEG, "-nostdin", "-v", "error", "-f", "lavfi", "-i",
            "sine=frequency=440:sample_rate=48000:duration=3",
            "-ac", "2", "-c:a", "alac", "-sample_fmt", "s32p", str(cls.fixture),
        ], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_dir.cleanup()

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="vm studio tests ")
        self.addCleanup(self.scratch.cleanup)
        self.directory = Path(self.scratch.name)
        self.repo = self.directory / "renderer with spaces"
        self.repo.mkdir()
        for filename in ("vm-studio", "verify-export.py"):
            shutil.copy2(ROOT / filename, self.repo / filename)
        core = self.repo / "vm-studio-lossless"
        core.write_text('''#!/bin/bash
set -eu
case "${CORE_MODE:-ok}" in
  fail) printf partial > "$2"; exit 7 ;;
  short) "$REAL_FFMPEG" -nostdin -v error -i "$FIXTURE" -t 0.25 -c:a alac -sample_fmt s32p "$2" ;;
  empty) : > "$2" ;;
  aac) "$REAL_FFMPEG" -nostdin -v error -i "$FIXTURE" -c:a aac "$2" ;;
  race) cp "$FIXTURE" "$2"; printf concurrent > "$RACE_DEST" ;;
  signal) cp "$FIXTURE" "$2"; kill -TERM "$PPID" ;;
  *) cp "$FIXTURE" "$2" ;;
esac
''')
        core.chmod(0o755)
        self.source = self.directory / "original memo.qta"
        shutil.copy2(self.fixture, self.source)
        self.source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.output = self.directory / "exports" / "lecture.ogg"
        # FFmpeg's ALAC encoder supports at most 24 bits. Apple writes 32-bit
        # ALAC, so only that field is simulated; audio and all other probes are real.
        probe_bin = self.directory / "probe-bin"
        probe_bin.mkdir()
        probe_script = probe_bin / "ffprobe"
        probe_script.write_text('''#!/usr/bin/env python3
import json, os, subprocess, sys
result = subprocess.run([os.environ["REAL_FFPROBE"], *sys.argv[1:]], capture_output=True)
if result.returncode:
    sys.stderr.buffer.write(result.stderr)
    sys.exit(result.returncode)
info = json.loads(result.stdout)
for audio in info.get("streams", []):
    if audio.get("codec_name") == "alac":
        audio["bits_per_raw_sample"] = "16" if os.environ.get("BAD_BITS") else "32"
print(json.dumps(info))
''')
        probe_script.chmod(0o755)
        self.env = dict(os.environ, FIXTURE=str(self.fixture), REAL_FFMPEG=FFMPEG,
                        REAL_FFPROBE=FFPROBE, PATH=str(probe_bin) + os.pathsep + os.environ["PATH"])

    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)
        self.assertEqual(list(self.directory.rglob(".vm-studio.*")), [])

    def run_wrapper(self, lossless=False, intensity="0.25", **env):
        args = [str(self.repo / "vm-studio")]
        if lossless:
            args.append("--lossless")
        args.extend([str(self.source), str(self.output), intensity])
        return subprocess.run(args, env=dict(self.env, **env), capture_output=True, text=True)

    def assert_failed(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.output.exists())

    def test_opus(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verified opus", result.stdout)
        self.assertTrue(self.output.is_file())

    def test_lossless(self):
        self.output = self.output.with_suffix(".m4a")
        result = self.run_wrapper(lossless=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), self.fixture.read_bytes())

    def test_existing_output_unchanged(self):
        self.output.parent.mkdir()
        self.output.write_text("precious previous export")
        result = self.run_wrapper()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), "precious previous export")

    def test_dangling_symlink_unchanged(self):
        self.output.parent.mkdir()
        self.output.symlink_to(self.directory / "missing")
        self.assertNotEqual(self.run_wrapper().returncode, 0)
        self.assertTrue(self.output.is_symlink())

    def test_source_as_output_unchanged(self):
        self.output = self.source
        self.assertNotEqual(self.run_wrapper().returncode, 0)

    def test_existing_directory_unchanged(self):
        self.output.mkdir(parents=True)
        self.assertNotEqual(self.run_wrapper().returncode, 0)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_invalid_intensities(self):
        for value in ("nan", "inf", "-0.1", "1.1", "garbage"):
            with self.subTest(value=value):
                self.assert_failed(self.run_wrapper(intensity=value))

    def test_renderer_failure(self):
        self.assert_failed(self.run_wrapper(CORE_MODE="fail"))

    def test_empty_render(self):
        self.assert_failed(self.run_wrapper(CORE_MODE="empty"))

    def test_truncated_render(self):
        self.assert_failed(self.run_wrapper(CORE_MODE="short"))

    def test_wrong_bit_depth(self):
        self.assert_failed(self.run_wrapper(BAD_BITS="1"))

    def test_wrong_codec(self):
        self.assert_failed(self.run_wrapper(CORE_MODE="aac"))

    def test_lossless_truncation(self):
        self.output = self.output.with_suffix(".m4a")
        self.assert_failed(self.run_wrapper(lossless=True, CORE_MODE="short"))

    def test_concurrent_destination_unchanged(self):
        result = self.run_wrapper(CORE_MODE="race", RACE_DEST=str(self.output))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_text(), "concurrent")

    def test_signal_does_not_publish(self):
        self.assert_failed(self.run_wrapper(CORE_MODE="signal"))

    def test_encoder_failure(self):
        fake_bin = self.directory / "bin"
        fake_bin.mkdir()
        executable = fake_bin / "ffmpeg"
        executable.write_text('''#!/bin/bash
for arg in "$@"; do
  if [[ "$arg" == libopus ]]; then exit 8; fi
done
exec "$REAL_FFMPEG" "$@"
''')
        executable.chmod(0o755)
        self.assert_failed(self.run_wrapper(PATH=str(fake_bin) + os.pathsep + self.env["PATH"]))

    def test_strict_decode_failure(self):
        fake_bin = self.directory / "bin"
        fake_bin.mkdir()
        executable = fake_bin / "ffmpeg"
        executable.write_text('''#!/bin/bash
for arg in "$@"; do
  if [[ "$arg" == null ]]; then exit 9; fi
done
exec "$REAL_FFMPEG" "$@"
''')
        executable.chmod(0o755)
        self.assert_failed(self.run_wrapper(PATH=str(fake_bin) + os.pathsep + self.env["PATH"]))

    def test_heredoc_stdin_remains_intact(self):
        for lossless in (False, True):
            with self.subTest(lossless=lossless):
                self.output = self.output.with_suffix(".m4a" if lossless else ".ogg")
                # shlex.quote protects spaces and literal shell characters in paths.
                import shlex
                command = [str(self.repo / "vm-studio")]
                if lossless:
                    command.append("--lossless")
                command += [str(self.source), str(self.output), "0.25"]
                script = "set -eu\n" + " ".join(map(shlex.quote, command)) + "\nprintf 'HEREDOC_SENTINEL\\n'\n"
                result = subprocess.run(["bash"], input=script, env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.endswith("HEREDOC_SENTINEL\n"))
                self.assertNotIn("Parse error", result.stderr)


if __name__ == "__main__":
    unittest.main()
