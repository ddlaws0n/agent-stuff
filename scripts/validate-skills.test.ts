import { afterEach, expect, test } from "bun:test";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { validateSkill } from "./validate-skills";

const FRONTMATTER =
  'name: sample\ndescription: Do a task when asked.\nlicense: MIT\nmetadata:\n  author: ddlaws0n\n  version: "0.1.0"';
const dirs: string[] = [];

async function fixture(
  frontmatter = FRONTMATTER,
  body = "# Sample\nDo the task.\n",
): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "skill-check-"));
  dirs.push(root);
  const directory = join(root, "sample");
  await mkdir(directory);
  await Promise.all([
    Bun.write(join(directory, "SKILL.md"), `---\n${frontmatter}\n---\n${body}`),
    Bun.write(join(directory, "LICENSE"), "MIT License\n"),
  ]);
  return directory;
}

afterEach(async () => {
  await Promise.all(
    dirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })),
  );
});

async function writeEvals(directory: string, data: unknown): Promise<void> {
  await mkdir(join(directory, "evals"));
  await Bun.write(join(directory, "evals", "evals.json"), JSON.stringify(data));
}

test("accepts a valid skill and eval corpus", async () => {
  const directory = await fixture();
  await writeEvals(directory, {
    skill_name: "sample",
    evals: [
      {
        id: 1,
        prompt: "Do the task",
        expected_output: "Task completed",
        files: ["SKILL.md"],
        assertions: ["An output exists"],
      },
    ],
  });
  expect(await validateSkill(directory)).toEqual([]);
});

test("rejects mismatched name, unquoted version and missing license", async () => {
  const directory = await fixture(
    "name: other\ndescription: Example\nmetadata:\n  author: ddlaws0n\n  version: 1.2",
  );
  await rm(join(directory, "LICENSE"));
  expect(await validateSkill(directory)).toEqual(
    expect.arrayContaining([
      expect.stringContaining("name must match"),
      expect.stringContaining("license must be MIT"),
      expect.stringContaining("missing bundled LICENSE"),
      expect.stringContaining("quoted SemVer"),
    ]),
  );
});

test("rejects duplicate eval IDs and escaping input paths", async () => {
  const directory = await fixture();
  await writeEvals(directory, {
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
  });
  expect(await validateSkill(directory)).toEqual(
    expect.arrayContaining([
      expect.stringContaining("files must be existing paths"),
      expect.stringContaining("unique positive integer id"),
    ]),
  );
});

test.each([
  {
    label: "invalid YAML",
    frontmatter: "name: [",
    body: "# Sample\n",
    message: "invalid YAML",
  },
  {
    label: "non-mapping frontmatter",
    frontmatter: "- sample",
    body: "# Sample\n",
    message: "frontmatter must be a mapping",
  },
  {
    label: "empty body",
    frontmatter: FRONTMATTER,
    body: "  \n",
    message: "SKILL.md body is empty",
  },
  {
    label: "invalid compatibility",
    frontmatter: `${FRONTMATTER}\ncompatibility: 123`,
    body: "# Sample\n",
    message: "compatibility must be a nonempty string",
  },
  {
    label: "non-string metadata",
    frontmatter: `${FRONTMATTER}\n  additional: 123`,
    body: "# Sample\n",
    message: "metadata values must be strings",
  },
])("rejects $label", async ({ frontmatter, body, message }) => {
  const directory = await fixture(frontmatter, body);
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining(message),
  ]);
});

test("rejects missing SKILL.md and missing frontmatter", async () => {
  const directory = await fixture();
  await Bun.write(join(directory, "SKILL.md"), "# Sample\n");
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining("needs YAML frontmatter"),
  ]);
  await rm(join(directory, "SKILL.md"));
  expect(await validateSkill(directory)).toEqual(["sample: missing SKILL.md"]);
});

test.each([
  {
    label: "empty eval corpus",
    data: { skill_name: "sample", evals: [] },
    message: "needs matching skill_name and a nonempty evals array",
  },
  {
    label: "directory instead of input file",
    data: {
      skill_name: "sample",
      evals: [
        { id: 1, prompt: "Do it", expected_output: "Done", files: ["evals"] },
      ],
    },
    message: "files must be existing paths within the skill",
  },
])("rejects $label", async ({ data, message }) => {
  const directory = await fixture();
  await writeEvals(directory, data);
  expect(await validateSkill(directory)).toEqual(
    expect.arrayContaining([expect.stringContaining(message)]),
  );
});

test("reports each invalid eval field", async () => {
  const directory = await fixture();
  await writeEvals(directory, {
    skill_name: "sample",
    evals: [{ id: 0, prompt: "", expected_output: "", assertions: [""] }],
  });
  expect(await validateSkill(directory)).toEqual([
    "sample: eval 1 needs a unique positive integer id",
    "sample: eval 1 needs a prompt",
    "sample: eval 1 needs expected_output",
    "sample: eval 1 assertions must be nonempty strings",
  ]);
});

test("reports malformed eval JSON", async () => {
  const directory = await fixture();
  await mkdir(join(directory, "evals"));
  await Bun.write(join(directory, "evals", "evals.json"), "{");
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining("invalid evals/evals.json"),
  ]);
});
