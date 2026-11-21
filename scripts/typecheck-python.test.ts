import { expect, test } from "bun:test";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pythonTypecheckArgs } from "./typecheck-python";

test("ty resolves configured project imports in standalone PEP 723 scripts", async () => {
  const root = await mkdtemp(join(tmpdir(), "skill-python-types-"));
  try {
    await mkdir(join(root, "eval/harness"), { recursive: true });
    await Bun.write(
      join(root, "ty.toml"),
      '[environment]\npython-version = "3.13"\nextra-paths = ["helper modules"]\n',
    );
    await Bun.write(
      join(root, "helper modules/bundled_helper.py"),
      "def answer() -> int:\n    return 42\n",
    );
    await Bun.write(
      join(root, "skills/sample/scripts/cli.py"),
      '# /// script\n# requires-python = ">=3.13"\n# dependencies = []\n# ///\nfrom bundled_helper import answer\nassert answer() == 42\n',
    );
    await Bun.write(
      join(root, "scripts/installed-skills/requirements.txt"),
      await Bun.file(
        join(import.meta.dir, "installed-skills/requirements.txt"),
      ).text(),
    );
    const args = await pythonTypecheckArgs(root);
    const previous = [...args];
    previous.splice(previous.indexOf("--extra-search-path"), 2);
    const broken = Bun.spawnSync(previous, { cwd: root });
    expect(broken.exitCode).toBe(1);
    expect(broken.stdout.toString() + broken.stderr.toString()).toContain(
      "unresolved-import",
    );
    const checked = Bun.spawnSync(args, { cwd: root });
    expect(checked.exitCode).toBe(0);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
