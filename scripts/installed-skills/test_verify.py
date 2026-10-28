"""Installed smoke discovery must not execute imported library modules as CLIs."""

import tempfile
import unittest
from pathlib import Path

import verify


class EntryPointTests(unittest.TestCase):
    def test_only_main_guard_entrypoints_are_run_through_python(self):
        with tempfile.TemporaryDirectory() as directory:
            skills = Path(directory)
            scripts = skills / "sample/scripts/nested"
            scripts.mkdir(parents=True)
            helper = scripts / "helper.py"
            helper.write_text('raise RuntimeError("Imported helpers are not standalone CLIs")\n')
            cli = scripts / "cli.py"
            cli.write_text('if __name__ == "__main__":\n    print("Fixture CLI help")\n')
            cli.chmod(0o644)
            entries = verify.python_entry_points(skills)
            self.assertEqual(entries, [cli])
            self.assertEqual(verify.run(entries[0], "--help").strip(), "Fixture CLI help")


if __name__ == "__main__":
    unittest.main()
