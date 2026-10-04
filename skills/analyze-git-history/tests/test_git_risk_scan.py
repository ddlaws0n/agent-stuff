from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "git-risk-scan.sh"


class GitRiskScanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        home = self.tmp / "home"
        home.mkdir()
        # Isolate from the developer's git config (signing, hooks, templates).
        self.env = {
            **os.environ,
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Alice",
            "GIT_AUTHOR_EMAIL": "alice@example.com",
            "GIT_COMMITTER_NAME": "Alice",
            "GIT_COMMITTER_EMAIL": "alice@example.com",
        }

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, repo: Path, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def new_repo(self, name: str = "repo") -> Path:
        repo = self.tmp / name
        repo.mkdir()
        self.git(repo, "init", "-q")
        return repo

    def commit(self, repo: Path, message: str, files: dict[str, str]) -> None:
        for name, text in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as handle:
                handle.write(text)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", message)

    def scan(self, repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT), "--path", str(repo), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    @staticmethod
    def section(report: str, title: str) -> str:
        match = re.search(rf"^## {re.escape(title)}.*?\n(.*?)(?=^## |\Z)", report, re.M | re.S)
        assert match, f"missing section {title!r}"
        return match.group(1)

    def test_many_files_do_not_crash_on_sigpipe(self):
        repo = self.new_repo()
        self.commit(repo, "fix: initial import", {f"src/file_{i:05}.txt": "x\n" for i in range(4000)})
        result = self.scan(repo, "--scope", "src", "--limit", "3")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.section(result.stdout, "Churn hotspots").strip().strip("`").split("\n")
        self.assertEqual(len([row for row in rows if row.strip()]), 3)

    def test_filenames_with_spaces_survive_the_overlap_join(self):
        repo = self.new_repo()
        self.commit(repo, "fix: crash", {"src/has space.py": "a\n"})
        self.commit(repo, "fix: another crash", {"src/has space.py": "b\n"})
        result = self.scan(repo, "--scope", "src")
        self.assertEqual(result.returncode, 0, result.stderr)
        overlap = self.section(result.stdout, "Files appearing in both")
        self.assertIn("src/has space.py  bug_touches=2 churn_touches=2", overlap)

    def test_keywords_match_whole_words_only(self):
        repo = self.new_repo()
        self.commit(repo, "add product page and prefix util", {"src/prefix.py": "a\n"})
        self.commit(repo, "fix(api): handle timeout", {"src/real.py": "a\n"})
        self.commit(repo, "Revert hotfix for prod outage", {"src/hot.py": "a\n"})
        result = self.scan(repo, "--scope", "src")
        self.assertEqual(result.returncode, 0, result.stderr)
        bugs = self.section(result.stdout, "Bug-fix hotspots")
        self.assertNotIn("prefix.py", bugs)
        self.assertIn("src/real.py", bugs)
        fire = self.section(result.stdout, "Firefighting commits")
        self.assertNotIn("product page", fire)
        self.assertIn("Revert hotfix", fire)

    def test_empty_repository_fails_cleanly(self):
        repo = self.new_repo()
        result = self.scan(repo)
        self.assertEqual(result.returncode, 4)
        self.assertEqual(result.stdout, "")
        self.assertIn("no commits", result.stderr)

    def test_path_outside_a_repository_fails_cleanly(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        result = self.scan(plain)
        self.assertEqual(result.returncode, 3)
        self.assertIn("not inside a git work tree", result.stderr)

    def test_shallow_clone_is_reported(self):
        origin = self.new_repo("origin")
        for i in range(3):
            self.commit(origin, f"change {i}", {"src/a.py": f"{i}\n"})
        clone = self.tmp / "clone"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", origin.as_uri(), str(clone)],
            env=self.env,
            check=True,
            capture_output=True,
        )
        result = self.scan(clone, "--scope", "src")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Shallow clone", self.section(result.stdout, "Warnings"))
        self.assertIn("Shallow clone", result.stderr)

    def test_paths_missing_from_head_are_skipped(self):
        repo = self.new_repo()
        self.commit(repo, "fix: gone bug", {"src/gone.py": "a\n", "src/kept.py": "a\n"})
        self.git(repo, "rm", "-q", "src/gone.py")
        self.git(repo, "commit", "-q", "-m", "fix: remove gone module")
        result = self.scan(repo, "--scope", "src")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("gone.py", self.section(result.stdout, "Churn hotspots"))
        self.assertNotIn("gone.py", self.section(result.stdout, "Bug-fix hotspots"))
        self.assertIn("src/kept.py", self.section(result.stdout, "Churn hotspots"))

    def test_generated_files_are_filtered_by_default(self):
        repo = self.new_repo()
        self.commit(repo, "fix: deps", {"package-lock.json": "{}\n", "src/dist/app.js": "x\n", "src/redist.py": "x\n"})
        churn = self.section(self.scan(repo).stdout, "Churn hotspots")
        self.assertNotIn("package-lock.json", churn)
        self.assertNotIn("src/dist/app.js", churn)
        self.assertIn("src/redist.py", churn)
        churn = self.section(self.scan(repo, "--include-generated").stdout, "Churn hotspots")
        self.assertIn("package-lock.json", churn)

    def test_scan_leaves_repository_unchanged(self):
        repo = self.new_repo()
        self.commit(repo, "fix: one", {"src/a.py": "a\n"})
        head = self.git(repo, "rev-parse", "HEAD")
        result = self.scan(repo, "--scope", "src")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git(repo, "status", "--porcelain", "--ignored"), "")
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), head)

    def test_rejects_invalid_limit(self):
        repo = self.new_repo()
        self.commit(repo, "init", {"a.py": "a\n"})
        self.assertEqual(self.scan(repo, "--limit", "0").returncode, 2)


if __name__ == "__main__":
    unittest.main()
