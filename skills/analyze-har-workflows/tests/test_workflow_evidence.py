"""Exercise the regression fixtures through the actual privacy-preserving inspector."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ROOT / "evals/files"


class WorkflowEvidenceTests(unittest.TestCase):
    def inspect(self, names, *args, code=0):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/har_inspect.py"),
                                 *[str(FILES / name) for name in names], *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_job_inventory_proves_two_shared_runs_without_disclosing_entities(self):
        out = self.inspect(["related-assignment.synthetic.har", "related-messaging.synthetic.har"],
                           "--select", "0:2:/jobs", "--select", "1:2:/jobs", "--walk", "--max-items", "200", "--max-chars", "30000")
        self.assertFalse(out["truncated"])
        rows = {(r["source"], r["pointer"]): r["value_id"] for r in out["observations"]}
        pairs = [(a, b) for a in range(3) for b in range(4)
                 if rows[0, f"/jobs/{a}/calling_job_id"] == rows[1, f"/jobs/{b}/root_job_id"]]
        self.assertEqual(pairs, [(0, 1), (2, 3)])
        callers = [rows[1, f"/jobs/{i}/calling_recipe_id"] for i in range(4)]
        self.assertNotEqual(callers[0], callers[1])
        self.assertEqual(callers[1:], [callers[1]] * 3)
        self.assertEqual(rows[0, "/jobs/0/title/account_id"], rows[0, "/jobs/2/title/account_id"])
        self.assertNotIn("private-account", json.dumps(out))
        self.assertNotIn("shared-run", json.dumps(out))
        counts = self.inspect(["related-assignment.synthetic.har", "related-messaging.synthetic.har"],
                              "--expect", "0:2:/job_scope_count", "7", "--expect", "1:2:/job_scope_count", "9",
                              "--expect", "0:2:/job_count", "43", "--expect", "1:2:/job_count", "50")
        self.assertTrue(all(row["matches"] for row in counts["checks"]))

    def test_separate_connections_share_an_environment_without_revealing_org(self):
        out = self.inspect(["related-assignment.synthetic.har", "related-messaging.synthetic.har"],
                           "--select", "0:3:/result/0/id", "--select", "1:3:/result/0/id",
                           "--select", "0:3:/result/0/input/org_id", "--select", "1:3:/result/0/input/org_id")
        rows = out["observations"]
        self.assertNotEqual(rows[0]["value_id"], rows[1]["value_id"])
        self.assertEqual(rows[2]["value_id"], rows[3]["value_id"])
        self.assertNotIn("private-same-org", json.dumps(out))

    def test_snapshot_equality_patch_locators_and_unselected_output_metadata(self):
        out = self.inspect(["definition-editing.synthetic.har"], "--select", "0:1:/result", "--select", "0:2:/result/recipe/code",
                           "--select", "0:3:/line_details/0/output/Opportunity/0/CombinedAttachments")
        self.assertEqual(out["observations"][0]["value_id"], out["observations"][1]["value_id"])
        self.assertIn("records", out["observations"][2]["keys"])
        self.assertNotIn("Private proposal", json.dumps(out))
        checks = self.inspect(["definition-editing.synthetic.har"],
                              "--expect", "0:1:/result/block/2/block/1/keyword", '"else"',
                              "--expect", "0:1:/result/block/2/block/1/block/0/provider", '"rest"',
                              "--expect", "0:1:/result/block/2/block/1/block/0/number", "6")
        self.assertTrue(all(row["matches"] for row in checks["checks"]))
        self.inspect(["definition-editing.synthetic.har"], "--expect", "0:1:/result/block/2/block/1/keyword", '"action"', code=1)


if __name__ == "__main__":
    unittest.main()
