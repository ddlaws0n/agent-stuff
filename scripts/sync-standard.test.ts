import { afterEach, expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { COPIES, header, run, syncStandard } from "./sync-standard";

// Deliberately not Prettier-shaped: JSON copies must survive byte for byte.
const SCHEMA = '{"$schema":"https://json-schema.org/draft/2020-12/schema" }';
const dirs: string[] = [];

async function tempDir(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "sync-standard-"));
  dirs.push(root);
  return root;
}

// A repository root holding only the sources the sync reads.
async function fixture(): Promise<string> {
  const root = await tempDir();
  const sources = new Set(COPIES.map((copy) => copy.source));
  await Promise.all(
    [...sources].map((source) =>
      Bun.write(
        join(root, source),
        source.endsWith(".json") ? SCHEMA : `# ${source}\n`,
      ),
    ),
  );
  return root;
}

// Runs the CLI entry point against a root and captures what it prints.
async function runQuietly(
  args: string[],
  root: string,
): Promise<{ code: number; out: string; err: string }> {
  const { log, warn, error } = console;
  const out: string[] = [];
  const err: string[] = [];
  console.log = (...parts: unknown[]) => void out.push(parts.join(" "));
  console.warn = console.error = (...parts: unknown[]) =>
    void err.push(parts.join(" "));
  try {
    const code = await run(args, root);
    return { code, out: out.join("\n"), err: err.join("\n") };
  } finally {
    Object.assign(console, { log, warn, error });
  }
}

afterEach(async () => {
  await Promise.all(
    dirs.splice(0).map((dir) => rm(dir, { recursive: true, force: true })),
  );
});

test("maps the standard onto four skills, five templates, and the schema", () => {
  expect(COPIES.map((copy) => copy.target)).toEqual([
    "skills/init-project-docs/references/standard.md",
    "skills/create-agentsmd/references/standard.md",
    "skills/maintain-project-docs/references/standard.md",
    "skills/update-changelog/references/standard.md",
    "skills/maintain-project-docs/assets/adr-template.md",
    "skills/maintain-project-docs/assets/plan-template.md",
    "skills/maintain-project-docs/assets/glossary-template.md",
    "skills/maintain-project-docs/assets/runbook-template.md",
    "skills/maintain-project-docs/assets/architecture-template.md",
    "skills/init-project-docs/assets/manifest.schema.json",
  ]);
});

test("writes Markdown copies under a header and JSON copies byte for byte", async () => {
  const root = await fixture();
  const result = await syncStandard(root, true);
  expect(result.missing).toEqual([]);
  expect(result.changed).toHaveLength(COPIES.length);

  const standard = await Bun.file(
    join(root, "skills/update-changelog/references/standard.md"),
  ).text();
  expect(standard).toBe(
    "<!-- Synced from standard/project-docs.md in ddlaws0n/agent-stuff. Do not edit here; edit the source and run bun run standard:sync. -->\n\n# standard/project-docs.md\n",
  );
  const template = await Bun.file(
    join(root, "skills/maintain-project-docs/assets/plan-template.md"),
  ).text();
  expect(template).toStartWith(header("standard/templates/plan.md"));
  expect(
    await Bun.file(
      join(root, "skills/init-project-docs/assets/manifest.schema.json"),
    ).text(),
  ).toBe(SCHEMA);
});

test("replaces an existing template and is idempotent", async () => {
  const root = await fixture();
  const adr = join(root, "skills/maintain-project-docs/assets/adr-template.md");
  await Bun.write(adr, "# ADR-[number]: [Decision]\n");
  await syncStandard(root, true);
  expect(await Bun.file(adr).text()).toContain("# standard/templates/adr.md");
  expect((await syncStandard(root, true)).changed).toEqual([]);
});

test("check lists drifted, edited, and missing copies without writing", async () => {
  const root = await fixture();
  await syncStandard(root, true);
  const edited = "skills/create-agentsmd/references/standard.md";
  const schema = "skills/init-project-docs/assets/manifest.schema.json";
  const removed = "skills/maintain-project-docs/assets/runbook-template.md";
  await Bun.write(join(root, edited), "# edited by hand\n");
  await Bun.write(join(root, schema), `${SCHEMA}\n`);
  await rm(join(root, removed));

  const result = await syncStandard(root, false);
  expect(result.changed.toSorted()).toEqual(
    [edited, removed, schema].toSorted(),
  );
  expect(await Bun.file(join(root, edited)).text()).toBe("# edited by hand\n");
  expect(await Bun.file(join(root, removed)).exists()).toBe(false);
});

test("reports missing sources and writes nothing", async () => {
  const root = await fixture();
  await rm(join(root, "standard/templates/glossary.md"));
  const result = await syncStandard(root, true);
  expect(result.missing).toEqual(["standard/templates/glossary.md"]);
  expect(result.changed).toEqual([]);
  expect(
    await Bun.file(
      join(root, "skills/init-project-docs/references/standard.md"),
    ).exists(),
  ).toBe(false);
});

test("fails on a template with no mapping and writes nothing", async () => {
  const root = await fixture();
  await Bun.write(join(root, "standard/templates/changelog.md"), "# New\n");
  for (const args of [[], ["--check"]]) {
    const { code, err } = await runQuietly(args, root);
    expect(code).toBe(1);
    expect(err).toContain("  standard/templates/changelog.md");
  }
  expect(
    await Bun.file(
      join(root, "skills/init-project-docs/references/standard.md"),
    ).exists(),
  ).toBe(false);
});

test("check fails on synced files the mapping does not produce", async () => {
  const root = await fixture();
  await syncStandard(root, true);
  const orphan = "skills/create-agentsmd/references/old-standard.md";
  await Bun.write(join(root, orphan), `${header("standard/old.md")}# Old\n`);
  await Bun.write(join(root, "skills/create-agentsmd/notes.md"), "# Notes\n");

  expect((await syncStandard(root, false)).orphans).toEqual([orphan]);
  const checked = await runQuietly(["--check"], root);
  expect(checked.code).toBe(1);
  expect(checked.err).toContain(`  ${orphan}`);
  expect(checked.err).not.toContain("notes.md");

  const synced = await runQuietly([], root);
  expect(synced.code).toBe(0);
  expect(synced.err).toContain(`  ${orphan}`);
  expect(await Bun.file(join(root, orphan)).exists()).toBe(true);
});

test("write mode lists the files it changed", async () => {
  const root = await fixture();
  const first = await runQuietly([], root);
  expect(first.code).toBe(0);
  expect(first.out).toStartWith("Updated 10 file(s) from standard/:");
  for (const { target } of COPIES) expect(first.out).toContain(`  ${target}`);

  const stale = "skills/update-changelog/references/standard.md";
  await Bun.write(join(root, stale), "stale\n");
  const second = await runQuietly([], root);
  expect(second.out).toBe(`Updated 1 file(s) from standard/:\n  ${stale}`);

  const third = await runQuietly([], root);
  expect(third.out).toStartWith("Synced copies already match standard/");
});

test("run exits non-zero on drift, missing sources, and unknown arguments", async () => {
  const root = await fixture();
  expect((await runQuietly(["--check"], root)).code).toBe(1);
  expect((await runQuietly([], root)).code).toBe(0);
  expect((await runQuietly(["--check"], root)).code).toBe(0);
  await Bun.write(
    join(root, "skills/update-changelog/references/standard.md"),
    "stale\n",
  );
  expect((await runQuietly(["--check"], root)).code).toBe(1);
  expect((await runQuietly(["--force"], root)).code).toBe(2);
  await rm(join(root, "standard"), { recursive: true });
  const missing = await runQuietly(["--check"], root);
  expect(missing.code).toBe(1);
  expect(missing.err).toContain("  standard/manifest.schema.json");
});
