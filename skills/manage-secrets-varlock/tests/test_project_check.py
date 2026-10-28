"""Exercise the shell wrapper with synthetic schemas and a local recording CLI."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/varlock-project-check.sh"


class ProjectCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".env.schema").write_text("# Synthetic schema, no credentials\n")
        binary = self.root / "node_modules/.bin/varlock"
        binary.parent.mkdir(parents=True)
        binary.write_text("""#!/bin/sh
printf '%s\\n' "$*" >> calls.txt
if [ "$1" = "load" ]; then
  printf '%s\\n' '{"fixture":"redacted"}'
  exit "${FIXTURE_LOAD_STATUS:-0}"
fi
""")
        binary.chmod(0o755)

    def invoke(self, *arguments, fail_load=False):
        return subprocess.run(["bash", str(SCRIPT), *arguments], cwd=self.root,
                              env={"PATH": os.defpath, "FIXTURE_LOAD_STATUS": "23" if fail_load else "0"},
                              text=True, capture_output=True, timeout=15)

    def calls(self):
        path = self.root / "calls.txt"
        return path.read_text().splitlines() if path.exists() else []

    def test_uses_local_cli_and_documented_redacted_load_then_audit_scan(self):
        result = self.invoke(str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), ["--version", "load --agent --format json-full", "audit", "scan"])
        self.assertIn('"fixture":"redacted"', result.stdout)

    def test_failed_load_stops_before_audit_or_scan(self):
        result = self.invoke(str(self.root), fail_load=True)
        self.assertEqual(result.returncode, 23)
        self.assertEqual(self.calls(), ["--version", "load --agent --format json-full"])

    def test_missing_schema_fails_before_using_cli(self):
        (self.root / ".env.schema").unlink()
        result = self.invoke(str(self.root))
        self.assertEqual(result.returncode, 11)
        self.assertIn(".env.schema not found", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_extra_argument_fails_without_using_cli(self):
        result = self.invoke(str(self.root), "extra")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
