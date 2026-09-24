from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "validate-workflows.py"
SPEC = importlib.util.spec_from_file_location("validate_workflows", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ValidateWorkflowsTests(unittest.TestCase):
    def validate(self, text: str, *, require_sha: bool = False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            path.write_text(text)
            return MODULE.validate_file(path, require_sha=require_sha)

    def codes(self, text: str, *, require_sha: bool = False) -> set[str]:
        return {finding.code for finding in self.validate(text, require_sha=require_sha)}

    def test_job_level_permissions_on_every_job_suppress_missing_warning(self):
        codes = self.codes("""name: CI
on: push
jobs:
  test:
    permissions:
      contents: read
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps: []
""")
        self.assertNotIn("permissions-missing", codes)

    def test_explicit_empty_top_permissions_is_a_boundary(self):
        codes = self.codes("""name: CI
on: push
permissions: {}
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps: []
""")
        self.assertNotIn("permissions-missing", codes)

    def test_reusable_workflow_floating_ref_is_rejected(self):
        codes = self.codes("""name: Reuse
on: workflow_dispatch
permissions: {}
jobs:
  call:
    uses: owner/repo/.github/workflows/deploy.yml@main
""")
        self.assertIn("uses-floating-ref", codes)

    def test_issue_comment_text_in_run_is_rejected(self):
        codes = self.codes("""name: Comment
on: issue_comment
permissions: {}
jobs:
  reply:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: echo '${{ github.event.comment.body }}'
""")
        self.assertIn("unsafe-event-expression-in-run", codes)

    def test_require_sha_applies_to_steps_and_reusable_workflows(self):
        findings = self.validate("""name: Strict
on: workflow_dispatch
permissions: {}
jobs:
  call:
    uses: owner/repo/.github/workflows/deploy.yml@v1
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v6
""", require_sha=True)
        self.assertEqual(2, sum(f.code == "uses-not-full-sha" for f in findings))


if __name__ == "__main__":
    unittest.main()
