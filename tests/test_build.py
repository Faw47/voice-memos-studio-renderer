"""Check that rebuilding cannot replace a working binary with compiler debris."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="vm studio build ")
        self.addCleanup(self.scratch.cleanup)
        self.directory = Path(self.scratch.name)
        shutil.copy2(ROOT / "Makefile", self.directory / "Makefile")
        (self.directory / "vm-studio-lossless.swift").write_text("test input")
        self.target = self.directory / "vm-studio-lossless"
        self.target.write_text("working binary")
        self.target.chmod(0o755)
        compiler = self.directory / "test-swiftc"
        compiler.write_text('''#!/bin/sh
set -eu
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then shift; output=$1; break; fi
  shift
done
printf 'new binary' > "$output"
[ "${BUILD_FAIL:-0}" = 0 ]
''')
        compiler.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.directory) + os.pathsep + os.environ["PATH"])

    def build(self, fail=False):
        return subprocess.run(
            ["make", "-B", "vm-studio-lossless", "SWIFTC=test-swiftc"],
            cwd=self.directory, env=dict(self.env, BUILD_FAIL="1" if fail else "0"),
            capture_output=True, text=True,
        )

    def tearDown(self):
        self.assertEqual(list(self.directory.glob(".vm-studio-lossless.*")), [])

    def test_failed_build_keeps_working_binary(self):
        result = self.build(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.target.read_text(), "working binary")

    def test_successful_build_publishes_executable(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), "new binary")
        self.assertTrue(os.access(self.target, os.X_OK))


if __name__ == "__main__":
    unittest.main()
