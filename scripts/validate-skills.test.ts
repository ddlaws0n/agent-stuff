import { afterEach, expect, test } from "bun:test";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { changedSkills, versionError } from "./check-skill-versions";
import {
  paddedTables,
  catalogSize,
  legacyHarEvals,
  pythonMetadataErrors,
  skillWarnings,
  triggerOverlapWarnings,
  validateRepository,
  validateSkill,
} from "./validate-skills";

const DESCRIPTION = "description: >-\n  Does a task. Use when asked.";
const METADATA = 'metadata:\n  author: ddlaws0n\n  version: "0.1.0"';
const FRONTMATTER = `name: sample\n${DESCRIPTION}\nlicense: MIT\n${METADATA}`;
const BODY = "# Sample\n\n## Workflow\n\n1. Do the task.\n";
const TRIGGERS = [
  { query: "Do the task", should_trigger: true },
  { query: "Do another task", should_trigger: false },
];
const dirs: string[] = [];

async function tempDir(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "skill-check-"));
  dirs.push(root);
  return root;
}

async function fixture(
  frontmatter = FRONTMATTER,
  body = BODY,
): Promise<string> {
  const directory = join(await tempDir(), "sample");
  await mkdir(directory);
  await Promise.all([
    Bun.write(join(directory, "SKILL.md"), `---\n${frontmatter}\n---\n${body}`),
    Bun.write(join(directory, "LICENSE"), "MIT License\n"),
    writeEvals(directory, {
      skill_name: "sample",
      evals: [
        {
          id: 1,
          prompt: "Do it",
          expected_output: "Done",
          assertions: ["The output exists"],
        },
      ],
    }),
    writeTriggers(directory, TRIGGERS),
  ]);
  return directory;
}

afterEach(async () => {
  await Promise.all(
    dirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })),
  );
});

async function writeEvals(directory: string, data: unknown): Promise<void> {
  // Most fixtures target unrelated checks; give them a normal/boundary corpus.
  // Schema-failure fixtures below write their exact JSON directly.
  if (
    data &&
    typeof data === "object" &&
    "evals" in data &&
    Array.isArray(data.evals)
  ) {
    const evals = data.evals.map((item: unknown, index: number) =>
      item && typeof item === "object"
        ? { tags: [index === 0 ? "normal" : "boundary"], ...item }
        : item,
    );
    if (evals.length === 1)
      evals.push({
        id: 999,
        prompt: "Handle a boundary",
        expected_output: "Boundary explained",
        tags: ["boundary"],
        assertions: ["The boundary is reported"],
      });
    data = {
      pressure: { required: false, reason: "Fixture has no approval gate." },
      ...data,
      evals,
    };
  }
  await Bun.write(join(directory, "evals", "evals.json"), JSON.stringify(data));
}

async function writeTriggers(directory: string, data: unknown): Promise<void> {
  await Bun.write(
    join(directory, "evals", "trigger-evals.json"),
    JSON.stringify(data),
  );
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

test("description length and late trigger guidance are advisory", async () => {
  const description = `Does ${"a".repeat(330)}. Use when ${"b".repeat(300)}.`;
  const directory = await fixture(
    FRONTMATTER.replace(DESCRIPTION, `description: >-\n  ${description}`),
  );
  expect(await validateSkill(directory)).toEqual([]);
  expect(await skillWarnings(directory)).toEqual([
    expect.stringContaining("editorial target: 600"),
    expect.stringContaining("editorial target: first 300"),
  ]);
  const size = catalogSize([
    {
      name: "sample",
      description: "Does a task.",
      path: "/skills/sample/SKILL.md",
    },
  ]);
  expect(size.namesAndDescriptions).toBe(18);
  expect(size.paths).toBe(23);
  expect(size.rendered).toBeGreaterThan(size.namesAndDescriptions + size.paths);
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
    body: BODY,
    message: "invalid YAML",
  },
  {
    label: "non-mapping frontmatter",
    frontmatter: "- sample",
    body: BODY,
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
    frontmatter: `name: sample\n${DESCRIPTION}\nlicense: MIT\ncompatibility: 123\n${METADATA}`,
    body: BODY,
    message: "compatibility must be a nonempty string",
  },
  {
    label: "extra metadata",
    frontmatter: `${FRONTMATTER}\n  domain: example`,
    body: BODY,
    message: "metadata may only contain author and version",
  },
  {
    label: "unsupported frontmatter key",
    frontmatter: `${FRONTMATTER}\nversion: "1"`,
    body: BODY,
    message: "unsupported frontmatter keys: version",
  },
  {
    label: "misordered frontmatter",
    frontmatter: `name: sample\nlicense: MIT\n${DESCRIPTION}\n${METADATA}`,
    body: BODY,
    message: "frontmatter keys must be ordered",
  },
  {
    label: "plain description",
    frontmatter: FRONTMATTER.replace(
      DESCRIPTION,
      "description: Does a task. Use when asked.",
    ),
    body: BODY,
    message: "folded block scalar",
  },
  {
    label: "trigger-first description",
    frontmatter: FRONTMATTER.replace("Does a task. Use", "Use this. Use"),
    body: BODY,
    message: 'then "Use when..."',
  },
  {
    label: "angle brackets in description",
    frontmatter: FRONTMATTER.replace("a task", "a <task>"),
    body: BODY,
    message: "must not contain < or >",
  },
  {
    label: "missing workflow section",
    frontmatter: FRONTMATTER,
    body: "# Sample\n\n## Steps\n",
    message: 'needs a "## Workflow" section',
  },
  {
    label: "missing referenced file",
    frontmatter: FRONTMATTER,
    body: `${BODY}\nRead \`assets/missing.md\`.\n`,
    message: "references missing assets/missing.md",
  },
  {
    label: "machine-specific path",
    frontmatter: FRONTMATTER,
    body: `${BODY}\nRun ~/.agents/skills/sample/run.sh.\n`,
    message: "SKILL.md contains a machine-specific path",
  },
  {
    label: "padded table",
    frontmatter: FRONTMATTER,
    body: `${BODY}\n| A | B |\n| --- | --- |\n| 1 | 2 |\n`,
    message: "SKILL.md:17 table separator must be compact",
  },
  {
    label: "overlong SKILL.md",
    frontmatter: FRONTMATTER,
    body: `${BODY}${"line\n".repeat(500)}`,
    message: "max 500",
  },
])("rejects $label", async ({ frontmatter, body, message }) => {
  const directory = await fixture(frontmatter, body);
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining(message),
  ]);
});

test("requires sections for bundled scripts and references", async () => {
  const directory = await fixture();
  await Bun.write(join(directory, "scripts", "run.py"), "print('hi')\n");
  await Bun.write(join(directory, "references", "more.md"), "# More\n");
  expect(await validateSkill(directory)).toEqual([
    'sample: SKILL.md needs a "## Scripts" section',
    'sample: SKILL.md needs a "## References" section',
    "sample: bundled scripts need discoverable tests (tests/**/test_*.py)",
  ]);
});

test("parses PEP 723 TOML and checks the documented Python minimum", () => {
  const source =
    '# /// script\n# requires-python = ">=3.10"\n# dependencies = []\n# ///\n';
  expect(pythonMetadataErrors(source, "Requires Python 3.10+.")).toEqual([]);
  expect(pythonMetadataErrors(source, "Requires Python 3.11+.")).toEqual([
    "requires-python must match compatibility minimum (>=3.11)",
  ]);
  expect(
    pythonMetadataErrors(
      source.replace(">=3.10", "broken"),
      "Requires Python 3.10+.",
    ),
  ).not.toEqual([]);
  expect(
    pythonMetadataErrors(source.replace("[]", "["), "Requires Python 3.10+."),
  ).toEqual(["PEP 723 metadata must be valid TOML"]);
  expect(
    pythonMetadataErrors(
      '# /// script\n# requires-python = ">=3.10"',
      "Requires Python 3.10+.",
    ),
  ).toEqual(["needs one complete PEP 723 script block"]);
});

test("checks real bundled command examples but exempts path mentions, fictional paths and helper modules", async () => {
  const directory = await fixture(
    FRONTMATTER,
    `${BODY}\n## Scripts\n\nSee \`scripts/tool.sh\`.\n- \`scripts/tool.sh show\` describes the selected command.\n\n\`bash scripts/tool.sh --help\`\n\n\`\`\`bash\nscripts/tool.sh --help\n\`\`\`\n\n## References\n\nSee \`references/examples.md\`.\n`,
  );
  await Bun.write(
    join(directory, "scripts", "tool.sh"),
    "#!/bin/bash\nexit 0\n",
  );
  await Bun.write(
    join(directory, "scripts", "helpers.py"),
    "def utility():\n    return 1\n",
  );
  await Bun.write(
    join(directory, "tests", "test_tool.py"),
    "import unittest\n",
  );
  await Bun.write(
    join(directory, "references", "examples.md"),
    "```bash\n./scripts/deploy.sh --dry-run\n```\n",
  );
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining("run scripts/tool.sh through its interpreter"),
  ]);
  await Bun.write(
    join(directory, "scripts", "helpers.py"),
    'if __name__ == "__main__":\n    print("hello")\n',
  );
  expect(await validateSkill(directory)).toEqual(
    expect.arrayContaining([
      expect.stringContaining(
        "helpers.py needs one complete PEP 723 script block",
      ),
    ]),
  );
});

test("explicit no-argument execution requires an interpreter while plain path references are valid", async () => {
  const directory = await fixture(
    FRONTMATTER,
    `${BODY}\n## Scripts\n\nSee \`scripts/tool.sh\`.\n\n\`scripts/tool.sh\`\n\nRun \`scripts/tool.sh\`.\n`,
  );
  await Bun.write(join(directory, "scripts/tool.sh"), "#!/bin/bash\nexit 0\n");
  await Bun.write(join(directory, "tests/test_tool.py"), "import unittest\n");
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining("run scripts/tool.sh through its interpreter"),
  ]);
});

test("rejects unexpected top-level files but ignores local artifacts", async () => {
  const directory = await fixture();
  await Bun.write(join(directory, "README.md"), "# Sample\n");
  await Bun.write(join(directory, ".DS_Store"), "\0");
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining("unexpected file README.md"),
  ]);
});

test("exempts eval fixtures from prose checks", async () => {
  const directory = await fixture();
  await Bun.write(
    join(directory, "evals", "files", "capture.md"),
    "/Users/someone\n| --- |\n",
  );
  expect(await validateSkill(directory)).toEqual([]);
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
    evals: [
      {
        id: 0,
        prompt: "",
        expected_output: "",
        assertions: [""],
        expectations: ["ignored"],
      },
    ],
  });
  expect(await validateSkill(directory)).toEqual([
    "sample: eval 1 needs a unique positive integer id",
    "sample: eval 1 needs a prompt",
    "sample: eval 1 needs expected_output",
    "sample: eval 1 assertions must be nonempty strings",
    "sample: eval 1 has unknown keys: expectations",
  ]);
});

test("requires assertions and valid tags without treating two labels as two cases", async () => {
  const normal = {
    id: 1,
    prompt: "Do the task",
    expected_output: "Output",
    assertions: ["Output exists"],
    tags: ["normal"],
  };
  const boundary = { ...normal, id: 2, tags: ["boundary"] };
  const policy = { required: false, reason: "No separate approval boundary." };
  for (const [evals, message] of [
    [
      [{ ...normal, assertions: undefined }, boundary],
      "assertions must be nonempty strings",
    ],
    [
      [{ ...normal, assertions: [] }, boundary],
      "assertions must be nonempty strings",
    ],
    [[{ ...normal, tags: undefined }, boundary], "tags must be unique values"],
    [[normal, { ...boundary, tags: ["typo"] }], "tags must be unique values"],
    [
      [normal, { ...boundary, tags: ["boundary", "boundary"] }],
      "tags must be unique values",
    ],
    [[{ ...normal, tags: ["normal", "boundary"] }], "needs distinct normal"],
  ] as const) {
    const directory = await fixture();
    await Bun.write(
      join(directory, "evals/evals.json"),
      JSON.stringify({ skill_name: "sample", pressure: policy, evals }),
    );
    expect(await validateSkill(directory)).toEqual(
      expect.arrayContaining([expect.stringContaining(message)]),
    );
  }
});

test("requires an explicit reviewed pressure decision and cases when required", async () => {
  const directory = await fixture();
  const evals = [
    {
      id: 1,
      prompt: "Normal",
      expected_output: "Output",
      assertions: ["Output exists"],
      tags: ["normal"],
    },
    {
      id: 2,
      prompt: "Boundary",
      expected_output: "Boundary",
      assertions: ["Boundary handled"],
      tags: ["boundary"],
    },
  ];
  for (const pressure of [
    undefined,
    { required: true, reason: "" },
    { required: "yes", reason: "Approval gate" },
  ]) {
    await Bun.write(
      join(directory, "evals/evals.json"),
      JSON.stringify({ skill_name: "sample", pressure, evals }),
    );
    expect(await validateSkill(directory)).toEqual(
      expect.arrayContaining([
        expect.stringContaining("reviewed for this skill"),
      ]),
    );
  }
  const pressure = {
    required: true,
    reason: "Approval gate must hold under urgency.",
  };
  await Bun.write(
    join(directory, "evals/evals.json"),
    JSON.stringify({ skill_name: "sample", pressure, evals }),
  );
  expect(await validateSkill(directory)).toEqual([
    "sample: pressure.required needs a pressure-tagged eval",
  ]);
  evals[1].tags.push("pressure");
  await Bun.write(
    join(directory, "evals/evals.json"),
    JSON.stringify({ skill_name: "sample", pressure, evals }),
  );
  expect(await validateSkill(directory)).toEqual([]);
});

test("normalizes duplicate trigger queries and flags conflicting labels", async () => {
  const directory = await fixture();
  for (const should_trigger of [true, false]) {
    await writeTriggers(directory, [
      ...TRIGGERS,
      { query: "  do  THE task\n", should_trigger },
    ]);
    const errors = await validateSkill(directory);
    expect(errors).toEqual([
      expect.stringContaining("duplicate trigger query"),
    ]);
    expect(errors[0].includes("conflicting should_trigger labels")).toBe(
      !should_trigger,
    );
  }
});

test("cross-skill positive trigger overlap is advisory", async () => {
  const root = await tempDir();
  await writeTriggers(join(root, "skills/a-skill"), TRIGGERS);
  await writeTriggers(join(root, "skills/b-skill"), [
    { query: " do THE task ", should_trigger: true },
  ]);
  expect(await triggerOverlapWarnings(root, ["a-skill", "b-skill"])).toEqual([
    expect.stringContaining("review whether collaboration is intended"),
  ]);
});

test("only the exact main HAR corpus receives the temporary schema exception", async () => {
  const source = await Bun.file(
    join(import.meta.dir, "fixtures/main-har-evals.json"),
  ).text();
  expect(legacyHarEvals("analyze-har-workflows", source)).toBe(true);
  expect(legacyHarEvals("sample", source)).toBe(false);
  expect(legacyHarEvals("analyze-har-workflows", `${source}\n`)).toBe(false);
  const directory = join(await tempDir(), "analyze-har-workflows");
  await Bun.write(
    join(directory, "SKILL.md"),
    `---\n${FRONTMATTER.replace("name: sample", "name: analyze-har-workflows")}\n---\n${BODY}`,
  );
  await Bun.write(join(directory, "LICENSE"), "MIT\n");
  await writeTriggers(directory, TRIGGERS);
  await Bun.write(join(directory, "evals/evals.json"), source);
  expect(
    (await validateSkill(directory)).some((error) =>
      /tags|pressure/.test(error),
    ),
  ).toBe(false);
  expect(await skillWarnings(directory)).toEqual([
    expect.stringContaining("temporary exact-corpus exception"),
  ]);
  await Bun.write(join(directory, "evals/evals.json"), `${source}\n`);
  expect(await validateSkill(directory)).toEqual(
    expect.arrayContaining([
      expect.stringContaining("reviewed for this skill"),
    ]),
  );
  expect(await skillWarnings(directory)).toEqual([]);
  const modern = {
    skill_name: "analyze-har-workflows",
    pressure: {
      required: true,
      reason: "Replay and privacy boundaries must hold under pressure.",
    },
    evals: [
      {
        id: 1,
        prompt: "Analyze a capture",
        expected_output: "Evidence",
        tags: ["normal"],
        assertions: ["Evidence is grounded"],
      },
      {
        id: 2,
        prompt: "Analyze under pressure",
        expected_output: "Boundary preserved",
        tags: ["pressure"],
        assertions: ["No unsupported replay is claimed"],
      },
    ],
  };
  const migrated = JSON.stringify(modern);
  expect(legacyHarEvals("analyze-har-workflows", migrated)).toBe(false);
  await Bun.write(join(directory, "evals/evals.json"), migrated);
  expect(await validateSkill(directory)).toEqual([]);
  expect(await skillWarnings(directory)).toEqual([]);
  modern.evals[1].assertions = [];
  await Bun.write(join(directory, "evals/evals.json"), JSON.stringify(modern));
  expect(await validateSkill(directory)).toEqual(
    expect.arrayContaining([
      expect.stringContaining("assertions must be nonempty"),
    ]),
  );
});

test("reports malformed and missing eval files", async () => {
  const directory = await fixture();
  await Bun.write(join(directory, "evals", "evals.json"), "{");
  await rm(join(directory, "evals", "trigger-evals.json"));
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining("invalid evals/evals.json"),
    "sample: missing evals/trigger-evals.json",
  ]);
});

test.each([
  {
    label: "malformed cases",
    data: [{ query: "", should_trigger: "yes" }],
    message: "must be an array of {query, should_trigger}",
  },
  {
    label: "one-sided cases",
    data: [TRIGGERS[0]],
    message: "needs should-trigger and near-miss cases",
  },
])("rejects trigger evals with $label", async ({ data, message }) => {
  const directory = await fixture();
  await writeTriggers(directory, data);
  expect(await validateSkill(directory)).toEqual([
    expect.stringContaining(message),
  ]);
});

test("finds padded table separators outside code fences", () => {
  const text = "|a|\n|-|\n\n```\n| --- |\n```\n|b|\n| :--- |\n";
  expect(paddedTables(text)).toEqual([8]);
});

test("requires an alphabetical README catalog and compact root tables", async () => {
  const root = await tempDir();
  await Bun.write(
    join(root, "README.md"),
    "| Skill |\n| ----- |\n| [`b-skill`](skills/b-skill/SKILL.md) |\n| [`a-skill`](skills/a-skill/SKILL.md) |\n",
  );
  expect(await validateRepository(root, ["a-skill", "b-skill"])).toEqual([
    "README.md: catalog must list skills alphabetically: a-skill, b-skill",
    "README.md:2 table separator must be compact (|-|-|)",
  ]);
});

test("maps changed paths to skills, ignoring dev-only directories", () => {
  expect(
    changedSkills([
      "skills/b/SKILL.md",
      "skills/a/scripts/run.py",
      "skills/c/evals/evals.json",
      "skills/c/tests/test_run.py",
      "docs/authoring.md",
      "",
    ]),
  ).toEqual(["a", "b"]);
});

test("requires a version increase for changed skills", () => {
  expect(versionError("a", "0.1.0", "0.1.0")).toContain("not greater");
  expect(versionError("a", "0.2.0", "0.1.9")).toContain("not greater");
  expect(versionError("a", "0.1.0", "0.1.1")).toBeUndefined();
  expect(versionError("a", undefined, "0.1.0")).toBeUndefined();
});
