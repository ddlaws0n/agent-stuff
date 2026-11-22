import { mkdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";

// Skills that bundle the standard as references/standard.md.
const STANDARD_SKILLS = [
  "init-project-docs",
  "create-agentsmd",
  "maintain-project-docs",
  "update-changelog",
];
const TEMPLATES = ["adr", "plan", "glossary", "runbook", "architecture"];
const REPOSITORY = "ddlaws0n/agent-stuff";
const SYNCED = "<!-- Synced from ";

// Paths are relative to the repository root. Markdown targets get a header;
// the JSON target is byte-identical.
export interface Copy {
  source: string;
  target: string;
}

export interface SyncResult {
  missing: string[]; // sources that do not exist
  unmapped: string[]; // standard/templates/*.md files that nothing copies
  orphans: string[]; // synced Markdown in skills/ that the mapping does not produce
  changed: string[]; // targets that were absent or differed from the expected copy
}

export const COPIES: Copy[] = [
  ...STANDARD_SKILLS.map((skill) => ({
    source: "standard/project-docs.md",
    target: `skills/${skill}/references/standard.md`,
  })),
  ...TEMPLATES.map((name) => ({
    source: `standard/templates/${name}.md`,
    target: `skills/maintain-project-docs/assets/${name}-template.md`,
  })),
  {
    source: "standard/manifest.schema.json",
    target: "skills/init-project-docs/assets/manifest.schema.json",
  },
];

export function header(source: string): string {
  return `${SYNCED}${source} in ${REPOSITORY}. Do not edit here; edit the source and run bun run standard:sync. -->\n\n`;
}

async function readBytes(path: string): Promise<Buffer | undefined> {
  const file = Bun.file(path);
  return (await file.exists())
    ? Buffer.from(await file.arrayBuffer())
    : undefined;
}

async function scan(root: string, pattern: string): Promise<string[]> {
  const paths: string[] = [];
  for await (const path of new Bun.Glob(pattern).scan({ cwd: root }))
    paths.push(path);
  return paths.toSorted();
}

// Compares every target with its expected copy. With `write`, rewrites the
// ones that differ, but only when every source exists and is mapped.
export async function syncStandard(
  root: string,
  write: boolean,
): Promise<SyncResult> {
  const sources = new Set(COPIES.map((copy) => copy.source));
  const targets = new Set(COPIES.map((copy) => copy.target));
  const unmapped = (await scan(root, "standard/templates/*.md")).filter(
    (path) => !sources.has(path),
  );
  const orphans: string[] = [];
  for (const path of await scan(root, "skills/**/*.md")) {
    const start = await Bun.file(join(root, path))
      .slice(0, SYNCED.length)
      .text();
    if (start === SYNCED && !targets.has(path)) orphans.push(path);
  }

  const missing = new Set<string>();
  const stale: { target: string; expected: Buffer }[] = [];
  for (const { source, target } of COPIES) {
    const bytes = await readBytes(join(root, source));
    if (!bytes) {
      missing.add(source);
      continue;
    }
    const expected = target.endsWith(".md")
      ? Buffer.concat([Buffer.from(header(source)), bytes])
      : bytes;
    if (!(await readBytes(join(root, target)))?.equals(expected))
      stale.push({ target, expected });
  }
  if (missing.size || unmapped.length)
    return { missing: [...missing], unmapped, orphans, changed: [] };

  if (write)
    for (const { target, expected } of stale) {
      await mkdir(dirname(join(root, target)), { recursive: true });
      await Bun.write(join(root, target), expected);
    }
  return {
    missing: [],
    unmapped,
    orphans,
    changed: stale.map((copy) => copy.target),
  };
}

function lines(title: string, paths: string[]): string {
  return `${title}\n${paths.map((path) => `  ${path}`).join("\n")}`;
}

export async function run(args: string[], root: string): Promise<number> {
  const unknown = args.filter((arg) => arg !== "--check");
  if (unknown.length) {
    console.error(
      `unknown arguments: ${unknown.join(" ")}\nusage: sync-standard.ts [--check]`,
    );
    return 2;
  }
  const check = args.includes("--check");
  const { missing, unmapped, orphans, changed } = await syncStandard(
    root,
    !check,
  );
  const errors: string[] = [];
  if (missing.length) errors.push(lines("missing standard sources:", missing));
  if (unmapped.length)
    errors.push(
      lines(
        "standard templates with no mapping in scripts/sync-standard.ts:",
        unmapped,
      ),
    );
  if (check && changed.length)
    errors.push(
      lines(
        `${changed.length} synced file(s) drifted from standard/; run bun run standard:sync:`,
        changed,
      ),
    );
  const orphaned = orphans.length
    ? lines(
        "synced files that standard/ no longer produces (fix or delete by hand):",
        orphans,
      )
    : "";
  if (check && orphaned) errors.push(orphaned);
  if (errors.length) {
    console.error(errors.join("\n"));
    return 1;
  }
  if (orphaned) console.warn(orphaned);
  console.log(
    changed.length
      ? lines(`Updated ${changed.length} file(s) from standard/:`, changed)
      : `Synced copies already match standard/ (${COPIES.length} files).`,
  );
  return 0;
}

if (import.meta.main) {
  process.exitCode = await run(
    Bun.argv.slice(2),
    resolve(import.meta.dir, ".."),
  );
}
