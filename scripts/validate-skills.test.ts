import { afterEach, expect, test } from "bun:test";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validateSkill } from "./validate-skills";

const dirs: string[] = [];
function fixture(
  frontmatter = 'name: sample\ndescription: Do a task when asked.\nlicense: MIT\nmetadata:\n  author: ddlaws0n\n  version: "0.1.0"',
) {
  const root = mkdtempSync(join(tmpdir(), "skill-check-"));
  dirs.push(root);
  const directory = join(root, "sample");
  mkdirSync(directory);
  writeFileSync(
    join(directory, "SKILL.md"),
    `---\n${frontmatter}\n---\n# Sample\nDo the task.\n`,
  );
  writeFileSync(join(directory, "LICENSE"), "MIT License\n");
  return directory;
}
afterEach(() => {
  for (const dir of dirs.splice(0))
    rmSync(dir, { recursive: true, force: true });
});

test("accepts a valid skill and eval corpus", () => {
  const directory = fixture();
  mkdirSync(join(directory, "evals"));
  writeFileSync(
    join(directory, "evals", "evals.json"),
    JSON.stringify({
      skill_name: "sample",
      evals: [
        {
          id: 1,
          prompt: "Do the task",
          expected_output: "Task completed",
          files: [],
          assertions: ["An output exists"],
        },
      ],
    }),
  );
  expect(validateSkill(directory)).toEqual([]);
});

test("rejects mismatched name, unquoted version and missing license", () => {
  const directory = fixture(
    "name: other\ndescription: Example\nmetadata:\n  author: ddlaws0n\n  version: 1.2",
  );
  expect(validateSkill(directory)).toEqual(
    expect.arrayContaining([
      expect.stringContaining("name must match"),
      expect.stringContaining("license must be MIT"),
      expect.stringContaining("quoted SemVer"),
    ]),
  );
});

test("rejects duplicate eval IDs and escaping input paths", () => {
  const directory = fixture();
  mkdirSync(join(directory, "evals"));
  writeFileSync(
    join(directory, "evals", "evals.json"),
    JSON.stringify({
      skill_name: "sample",
      evals: [
        {
          id: 1,
          prompt: "Do it",
          expected_output: "Done",
          files: ["../outside"],
        },
        { id: 1, prompt: "Again", expected_output: "Done" },
      ],
    }),
  );
  expect(validateSkill(directory)).toEqual(
    expect.arrayContaining([
      expect.stringContaining("files must be existing paths"),
      expect.stringContaining("unique positive integer id"),
    ]),
  );
});
