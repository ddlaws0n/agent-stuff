import { afterEach, expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const directories: string[] = [];
afterEach(async () => {
  await Promise.all(
    directories
      .splice(0)
      .map((path) => rm(path, { recursive: true, force: true })),
  );
});

const runner = (directory: string) => [
  "uv",
  "run",
  "--no-project",
  "python",
  "-B",
  resolve(import.meta.dir, "run-python-tests.py"),
  directory,
];

test("Python runner rejects empty discovery and propagates real test failures", async () => {
  const directory = await mkdtemp(join(tmpdir(), "skill-tests-"));
  directories.push(directory);
  const command = runner(directory);
  const empty = Bun.spawnSync(command);
  expect(empty.exitCode).toBe(2);
  expect(empty.stderr.toString()).toContain("No tests collected");
  await Bun.write(
    join(directory, "test_contract.py"),
    "import unittest\nclass Contract(unittest.TestCase):\n    def test_contract(self):\n        self.assertEqual(1, 2)\n",
  );
  expect(Bun.spawnSync(command).exitCode).toBe(1);
  await Bun.write(
    join(directory, "test_contract.py"),
    "import unittest\nclass Contract(unittest.TestCase):\n    def test_contract(self):\n        self.assertEqual(1, 1)\n",
  );
  expect(Bun.spawnSync(command).exitCode).toBe(0);
});

test("Python test descendants do not leave stale bytecode", async () => {
  const directory = await mkdtemp(join(tmpdir(), "skill-bytecode-"));
  directories.push(directory);
  await Bun.write(join(directory, "bytecode_fixture.py"), "VALUE = 42\n");
  await Bun.write(
    join(directory, "test_descendants.py"),
    `import subprocess
import sys
import unittest
from pathlib import Path

class Descendants(unittest.TestCase):
    def test_imports_in_children(self):
        child = 'import subprocess, sys, bytecode_fixture; subprocess.run([sys.executable, "-c", "import bytecode_fixture"], check=True)'
        subprocess.run([sys.executable, "-c", child], cwd=Path(__file__).parent, check=True)
`,
  );
  const result = Bun.spawnSync(runner(directory), {
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: undefined },
  });
  expect(result.exitCode).toBe(0);
  expect([...new Bun.Glob("**/*.pyc").scanSync({ cwd: directory })]).toEqual(
    [],
  );
});
