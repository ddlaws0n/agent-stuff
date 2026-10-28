import { access, readdir } from "node:fs/promises";
import { basename, isAbsolute, join, relative, resolve, sep } from "node:path";
import { type Document, isScalar, parseDocument, Scalar } from "yaml";

const NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SEMVER =
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;
// Canonical frontmatter order; `allowed-tools` is in the spec but experimental.
const FRONTMATTER_KEYS = [
  "name",
  "description",
  "license",
  "compatibility",
  "metadata",
  "allowed-tools",
];
const METADATA_KEYS = new Set(["author", "version"]);
const EVAL_KEYS = new Set([
  "id",
  "name",
  "prompt",
  "expected_output",
  "files",
  "assertions",
  "tags",
]);
const EVAL_TAGS = new Set([
  "normal",
  "boundary",
  "refusal",
  "dry-run",
  "pressure",
]);
// Remove after the HAR branch's corpus migration lands. Only the exact corpus
// on main can defer tags/pressure; assertions and all other checks still apply.
const LEGACY_HAR_EVAL_SHA256 =
  "5d6ec64d8a4f4f4d0babbdfe6ccf69e8e1a4ec95ceb5f9d17427cd57b209bb77";

export function legacyHarEvals(name: string, text: string): boolean {
  return (
    name === "analyze-har-workflows" &&
    new Bun.CryptoHasher("sha256").update(text).digest("hex") ===
      LEGACY_HAR_EVAL_SHA256
  );
}

export function normalizeQuery(query: string): string {
  return query.normalize("NFKC").trim().replace(/\s+/g, " ").toLowerCase();
}

function validTags(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(
      (tag: unknown) => typeof tag === "string" && EVAL_TAGS.has(tag),
    ) &&
    new Set(value).size === value.length
  );
}
const SKILL_ENTRIES = new Set([
  "SKILL.md",
  "LICENSE",
  "assets",
  "evals",
  "references",
  "scripts",
  "tests",
]);
// Git-ignored local artifacts that never reach installations.
const IGNORED_ENTRIES = new Set([".DS_Store", "__pycache__"]);
// Byte-for-byte evaluation inputs are exempt from prose checks.
const FIXTURE_DIRS = [join("evals", "files"), join("evals", "fixtures")];
const MAX_SKILL_LINES = 500;
const MACHINE_PATH = /~\/[\w.]|\/Users\/|\/home\/|[A-Za-z]:\\Users\\/;
const TABLE_SEPARATOR = /^\|(?:\s*:?-+:?\s*\|)+\s*$/;
const COMPACT_SEPARATOR = /^\|(?::?-:?\|)+$/;
const RESOURCE_PATH = /\b(?:assets|references|scripts)\/[\w./-]*\w/g;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateMetadata(
  data: Record<string, unknown>,
  document: Document,
  name: string,
): string[] {
  const errors: string[] = [];
  const keys = Object.keys(data);
  const unknown = keys.filter((key) => !FRONTMATTER_KEYS.includes(key));
  if (unknown.length)
    errors.push(`${name}: unsupported frontmatter keys: ${unknown.join(", ")}`);
  const known = keys.filter((key) => FRONTMATTER_KEYS.includes(key));
  const ordered = FRONTMATTER_KEYS.filter((key) => known.includes(key));
  if (known.join() !== ordered.join())
    errors.push(
      `${name}: frontmatter keys must be ordered ${ordered.join(", ")}`,
    );

  if (
    typeof data.name !== "string" ||
    data.name !== name ||
    data.name.length > 64 ||
    !NAME.test(data.name)
  ) {
    errors.push(
      `${name}: name must match its lowercase-hyphenated directory (max 64 characters)`,
    );
  }
  if (
    typeof data.description !== "string" ||
    !data.description.trim() ||
    data.description.length > 1024
  ) {
    errors.push(
      `${name}: description must be a nonempty string of at most 1024 characters`,
    );
  } else {
    const node = document.get("description", true);
    if (!isScalar(node) || node.type !== Scalar.BLOCK_FOLDED)
      errors.push(`${name}: description must be a folded block scalar (>-)`);
    if (/[<>]/.test(data.description))
      errors.push(`${name}: description must not contain < or >`);
    if (
      data.description.startsWith("Use ") ||
      !/\bUse when\b/.test(data.description)
    )
      errors.push(
        `${name}: description must state what the skill does, then "Use when..."`,
      );
  }
  if (data.license !== "MIT") errors.push(`${name}: license must be MIT`);
  if (
    data.compatibility !== undefined &&
    (typeof data.compatibility !== "string" ||
      !data.compatibility.trim() ||
      data.compatibility.length > 500)
  ) {
    errors.push(
      `${name}: compatibility must be a nonempty string of at most 500 characters`,
    );
  }
  if (
    !isRecord(data.metadata) ||
    data.metadata.author !== "ddlaws0n" ||
    typeof data.metadata.version !== "string" ||
    !SEMVER.test(data.metadata.version)
  ) {
    errors.push(
      `${name}: metadata requires author: ddlaws0n and a quoted SemVer version`,
    );
  } else if (
    Object.keys(data.metadata).some((key) => !METADATA_KEYS.has(key))
  ) {
    errors.push(`${name}: metadata may only contain author and version`);
  }
  return errors;
}

function exists(path: string): Promise<boolean> {
  return access(path).then(
    () => true,
    () => false,
  );
}

export function isPythonEntryPoint(source: string): boolean {
  return /^if\s+__name__\s*==\s*["']__main__["']\s*:/m.test(source);
}

export function pythonMinimum(compatibility: unknown): string | undefined {
  return typeof compatibility === "string"
    ? /\bPython (\d+\.\d+)\+/.exec(compatibility)?.[1]
    : undefined;
}

// Lenient frontmatter read for advisory checks; validateSkill reports errors.
export async function readFrontmatter(
  directory: string,
): Promise<Record<string, unknown>> {
  const source = await Bun.file(join(directory, "SKILL.md")).text();
  const match = /^---\r?\n([\s\S]*?)\r?\n---/.exec(source);
  const data: unknown = match ? parseDocument(match[1]).toJS() : null;
  return isRecord(data) ? data : {};
}

export function pythonMetadataErrors(
  source: string,
  compatibility: unknown,
): string[] {
  const blocks = [
    ...source.matchAll(/^# \/\/\/ script\r?\n([\s\S]*?)^# \/\/\/\s*$/gm),
  ];
  if (blocks.length !== 1) return ["needs one complete PEP 723 script block"];
  const lines = blocks[0][1].trimEnd().split(/\r?\n/);
  if (lines.some((line) => !/^#(?: |$)/.test(line)))
    return ["PEP 723 metadata must contain only comment lines"];
  let metadata: Record<string, unknown>;
  try {
    const parsed: unknown = Bun.TOML.parse(
      lines.map((line) => line.slice(2)).join("\n"),
    );
    if (!isRecord(parsed)) return ["PEP 723 metadata must be a TOML mapping"];
    metadata = parsed;
  } catch {
    return ["PEP 723 metadata must be valid TOML"];
  }
  const minimum = pythonMinimum(compatibility);
  const errors: string[] = [];
  if (!minimum) errors.push("compatibility must declare a Python X.Y+ minimum");
  else if (metadata["requires-python"] !== `>=${minimum}`)
    errors.push(
      `requires-python must match compatibility minimum (>=${minimum})`,
    );
  if (
    metadata.dependencies !== undefined &&
    (!Array.isArray(metadata.dependencies) ||
      metadata.dependencies.some(
        (dependency) => typeof dependency !== "string" || !dependency.trim(),
      ))
  )
    errors.push("PEP 723 dependencies must be an array of nonempty strings");
  return errors;
}

async function interpreterErrors(
  text: string,
  directory: string,
  path: string,
): Promise<string[]> {
  const errors: string[] = [];
  let fenceLanguage: string | undefined;
  let shellFence = false;
  for (const [index, line] of text.split("\n").entries()) {
    const fence = /^\s*(?:```|~~~)(\w*)/.exec(line);
    if (fence) {
      fenceLanguage = fenceLanguage === undefined ? fence[1] : undefined;
      shellFence =
        fenceLanguage !== undefined &&
        ["", "bash", "sh", "shell", "console"].includes(fenceLanguage);
      continue;
    }
    const candidates = [...line.matchAll(/`([^`]+)`/g)]
      .filter((match) => {
        const before = line.slice(0, match.index).trim();
        const after = line.slice(match.index + match[0].length).trim();
        return (
          /\b(?:run|execute|invoke|command(?: is)?|usage:)\s*$/i.test(before) ||
          (!after &&
            /^(?:[-*]\s*)?$/.test(before) &&
            /^\S+\s+\S/.test(match[1]))
        );
      })
      .map((match) => match[1]);
    // Inline labels that explain a subcommand are references. Only explicit
    // execution instructions or standalone examples count as commands.
    if (shellFence || !path.endsWith(".md"))
      candidates.push(line.trim().replace(/^Usage:\s*/, ""));
    for (const command of candidates) {
      const match = /^(?:\$\s+)?(?:\.\/)?(scripts\/[\w./-]+)(.*)$/.exec(
        command,
      );
      if (!match) continue;
      if (await exists(join(directory, match[1]))) {
        errors.push(
          `${path}:${index + 1} run ${match[1]} through its interpreter`,
        );
        break;
      }
    }
  }
  return errors;
}

async function validateScripts(
  directory: string,
  name: string,
  compatibility: unknown,
): Promise<string[]> {
  const scripts = [
    ...new Bun.Glob("scripts/**/*.{py,sh}").scanSync({ cwd: directory }),
  ];
  if (!scripts.length) return [];
  const errors: string[] = [];
  if (
    ![...new Bun.Glob("tests/**/test_*.py").scanSync({ cwd: directory })].length
  )
    errors.push(
      `${name}: bundled scripts need discoverable tests (tests/**/test_*.py)`,
    );
  for (const script of scripts.filter((path) => path.endsWith(".py"))) {
    const source = await Bun.file(join(directory, script)).text();
    if (isPythonEntryPoint(source))
      errors.push(
        ...pythonMetadataErrors(source, compatibility).map(
          (error) => `${name}: ${script} ${error}`,
        ),
      );
  }
  return errors;
}

async function validateBody(
  text: string,
  body: string,
  name: string,
  directory: string,
): Promise<string[]> {
  if (!body.trim()) return [`${name}: SKILL.md body is empty`];
  const errors: string[] = [];
  const lines = text.split("\n").length;
  if (lines > MAX_SKILL_LINES)
    errors.push(
      `${name}: SKILL.md has ${lines} lines (max ${MAX_SKILL_LINES}); move detail to references/`,
    );
  const headings = new Set(
    stripFences(body)
      .filter((line) => line.startsWith("## "))
      .map((line) => line.slice(3).trim()),
  );
  const sections: [string, string | undefined][] = [
    ["Workflow", undefined],
    ["Scripts", "scripts"],
    ["References", "references"],
  ];
  for (const [heading, folder] of sections) {
    if (folder && !(await exists(join(directory, folder)))) continue;
    if (!headings.has(heading))
      errors.push(`${name}: SKILL.md needs a "## ${heading}" section`);
  }
  for (const path of new Set(body.match(RESOURCE_PATH))) {
    if (!(await exists(join(directory, path))))
      errors.push(`${name}: SKILL.md references missing ${path}`);
  }
  return errors;
}

// Lines outside fenced code blocks; fence contents are examples, not prose.
function stripFences(text: string): string[] {
  let fence = false;
  return text.split("\n").filter((line) => {
    if (/^\s*(```|~~~)/.test(line)) {
      fence = !fence;
      return false;
    }
    return !fence;
  });
}

export function paddedTables(text: string): number[] {
  let fence = false;
  const lines: number[] = [];
  for (const [index, line] of text.split("\n").entries()) {
    if (/^\s*(```|~~~)/.test(line)) fence = !fence;
    else if (
      !fence &&
      TABLE_SEPARATOR.test(line) &&
      !COMPACT_SEPARATOR.test(line)
    )
      lines.push(index + 1);
  }
  return lines;
}

async function validateFiles(
  directory: string,
  name: string,
): Promise<string[]> {
  const errors: string[] = [];
  for (const entry of await readdir(directory)) {
    if (!SKILL_ENTRIES.has(entry) && !IGNORED_ENTRIES.has(entry))
      errors.push(
        `${name}: unexpected file ${entry}; skills may only contain ${[...SKILL_ENTRIES].join(", ")}`,
      );
  }
  for await (const path of new Bun.Glob("**/*").scan({ cwd: directory })) {
    if (
      path.split(sep).some((part) => IGNORED_ENTRIES.has(part)) ||
      FIXTURE_DIRS.some((dir) => path.startsWith(dir + sep))
    )
      continue;
    const text = await Bun.file(join(directory, path)).text();
    if (text.includes("\0")) continue;
    if (MACHINE_PATH.test(text))
      errors.push(`${name}: ${path} contains a machine-specific path`);
    if (/\.(?:md|py|sh)$/.test(path))
      errors.push(
        ...(await interpreterErrors(text, directory, path)).map(
          (error) => `${name}: ${error}`,
        ),
      );
    if (path.endsWith(".md"))
      for (const line of paddedTables(text))
        errors.push(
          `${name}: ${path}:${line} table separator must be compact (|-|-|)`,
        );
  }
  return errors;
}

async function validFiles(directory: string, value: unknown): Promise<boolean> {
  if (!Array.isArray(value)) return false;
  const files: unknown[] = value;
  for (const file of files) {
    if (typeof file !== "string" || !file || isAbsolute(file)) return false;
    const path = resolve(directory, file);
    const within = relative(directory, path);
    if (within === ".." || within.startsWith(`..${sep}`)) return false;
    const input = Bun.file(path);
    if (!(await input.exists()) || !(await input.stat()).isFile()) return false;
  }
  return true;
}

async function validateEvals(
  directory: string,
  name: string,
): Promise<string[]> {
  const evalFile = Bun.file(join(directory, "evals", "evals.json"));
  if (!(await evalFile.exists())) return [`${name}: missing evals/evals.json`];

  const errors: string[] = [];
  try {
    const source = await evalFile.text();
    const legacy = legacyHarEvals(name, source);
    const evals: unknown = JSON.parse(source);
    if (
      !isRecord(evals) ||
      evals.skill_name !== name ||
      !Array.isArray(evals.evals) ||
      evals.evals.length === 0
    ) {
      return [
        `${name}: evals/evals.json needs matching skill_name and a nonempty evals array`,
      ];
    }

    const ids = new Set<number>();
    const items: unknown[] = evals.evals;
    const taggedCases: string[][] = [];
    if (
      !legacy &&
      (!isRecord(evals.pressure) ||
        typeof evals.pressure.required !== "boolean" ||
        typeof evals.pressure.reason !== "string" ||
        !evals.pressure.reason.trim())
    )
      errors.push(
        `${name}: eval corpus needs pressure {required: boolean, reason: nonempty string} reviewed for this skill`,
      );
    for (const [index, item] of items.entries()) {
      const prefix = `${name}: eval ${index + 1}`;
      if (!isRecord(item)) {
        errors.push(`${prefix} must be an object`);
        continue;
      }
      if (
        typeof item.id !== "number" ||
        !Number.isSafeInteger(item.id) ||
        item.id < 1 ||
        ids.has(item.id)
      ) {
        errors.push(`${prefix} needs a unique positive integer id`);
      } else ids.add(item.id);
      if (typeof item.prompt !== "string" || !item.prompt.trim())
        errors.push(`${prefix} needs a prompt`);
      if (
        typeof item.expected_output !== "string" ||
        !item.expected_output.trim()
      )
        errors.push(`${prefix} needs expected_output`);
      if (
        item.files !== undefined &&
        !(await validFiles(directory, item.files))
      )
        errors.push(`${prefix} files must be existing paths within the skill`);
      if (
        !Array.isArray(item.assertions) ||
        item.assertions.length === 0 ||
        item.assertions.some(
          (assertion: unknown) =>
            typeof assertion !== "string" || !assertion.trim(),
        )
      ) {
        errors.push(`${prefix} assertions must be nonempty strings`);
      }
      if (!legacy) {
        if (!validTags(item.tags))
          errors.push(
            `${prefix} tags must be unique values from ${[...EVAL_TAGS].join(", ")}`,
          );
        else taggedCases.push(item.tags);
      }
      // Unknown keys (e.g. "expectations") would otherwise be silently skipped.
      const unknown = Object.keys(item).filter((key) => !EVAL_KEYS.has(key));
      if (unknown.length > 0)
        errors.push(`${prefix} has unknown keys: ${unknown.join(", ")}`);
    }
    if (!legacy) {
      const normal = taggedCases.flatMap((tags, index) =>
        tags.includes("normal") ? [index] : [],
      );
      const boundaries = taggedCases.flatMap((tags, index) =>
        tags.some((tag) => tag !== "normal") ? [index] : [],
      );
      if (!normal.some((index) => boundaries.some((other) => other !== index)))
        errors.push(
          `${name}: needs distinct normal and boundary/refusal/dry-run/pressure eval cases`,
        );
      if (
        isRecord(evals.pressure) &&
        evals.pressure.required === true &&
        !taggedCases.some((tags) => tags.includes("pressure"))
      )
        errors.push(`${name}: pressure.required needs a pressure-tagged eval`);
    }
  } catch (error) {
    errors.push(`${name}: invalid evals/evals.json: ${String(error)}`);
  }
  return errors;
}

async function validateTriggerEvals(
  directory: string,
  name: string,
): Promise<string[]> {
  const file = Bun.file(join(directory, "evals", "trigger-evals.json"));
  if (!(await file.exists()))
    return [`${name}: missing evals/trigger-evals.json`];
  try {
    const cases: unknown = await file.json();
    if (
      !Array.isArray(cases) ||
      cases.some(
        (item: unknown) =>
          !isRecord(item) ||
          typeof item.query !== "string" ||
          !item.query.trim() ||
          typeof item.should_trigger !== "boolean",
      )
    )
      return [
        `${name}: trigger-evals.json must be an array of {query, should_trigger}`,
      ];
    const validCases: { query: string; should_trigger: boolean }[] = cases;
    const expected = new Set(validCases.map((item) => item.should_trigger));
    if (expected.size < 2)
      return [
        `${name}: trigger-evals.json needs should-trigger and near-miss cases`,
      ];
    const seen = new Map<string, boolean>();
    const errors: string[] = [];
    for (const item of validCases) {
      const query = normalizeQuery(item.query);
      if (seen.has(query))
        errors.push(
          `${name}: duplicate trigger query ${JSON.stringify(item.query)}${seen.get(query) !== item.should_trigger ? " has conflicting should_trigger labels" : ""}`,
        );
      seen.set(query, item.should_trigger);
    }
    return errors;
  } catch (error) {
    return [`${name}: invalid evals/trigger-evals.json: ${String(error)}`];
  }
}

export async function validateSkill(directory: string): Promise<string[]> {
  const name = basename(directory);
  const skillFile = Bun.file(join(directory, "SKILL.md"));
  if (!(await skillFile.exists())) return [`${name}: missing SKILL.md`];

  const text = await skillFile.text();
  const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/.exec(text);
  if (!frontmatter)
    return [`${name}: SKILL.md needs YAML frontmatter and a Markdown body`];

  const document = parseDocument(frontmatter[1], { uniqueKeys: true });
  const yamlErrors = document.errors.map(
    (error) => `${name}: invalid YAML: ${error.message}`,
  );
  if (yamlErrors.length) return yamlErrors;
  const data: unknown = document.toJS();
  if (!isRecord(data)) return [`${name}: frontmatter must be a mapping`];

  const errors = validateMetadata(data, document, name);
  if (!(await Bun.file(join(directory, "LICENSE")).exists()))
    errors.push(`${name}: missing bundled LICENSE`);
  const results = await Promise.all([
    validateBody(text, frontmatter[2], name, directory),
    validateFiles(directory, name),
    validateEvals(directory, name),
    validateTriggerEvals(directory, name),
    validateScripts(directory, name, data.compatibility),
  ]);
  return errors.concat(...results);
}

// Repository-level checks: the README catalog lists every skill, sorted, and
// root documentation keeps compact tables.
export async function validateRepository(
  root: string,
  skills: string[],
): Promise<string[]> {
  const errors: string[] = [];
  const readme = await Bun.file(join(root, "README.md")).text();
  const catalog = [
    ...readme.matchAll(/^\| \[`([a-z0-9-]+)`\]\(skills\//gm),
  ].map((match) => match[1]);
  if (catalog.join() !== skills.join())
    errors.push(
      `README.md: catalog must list skills alphabetically: ${skills.join(", ")}`,
    );
  for (const pattern of ["*.md", "docs/**/*.md"]) {
    for await (const path of new Bun.Glob(pattern).scan({ cwd: root })) {
      for (const line of paddedTables(await Bun.file(join(root, path)).text()))
        errors.push(`${path}:${line} table separator must be compact (|-|-|)`);
    }
  }
  return errors;
}

export async function skillDirectories(skillsDir: string): Promise<string[]> {
  const entries = await readdir(skillsDir, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .toSorted();
}

export async function skillWarnings(directory: string): Promise<string[]> {
  const name = basename(directory);
  const data = await readFrontmatter(directory);
  if (typeof data.description !== "string") return [];
  const warnings: string[] = [];
  const evalFile = Bun.file(join(directory, "evals", "evals.json"));
  if ((await evalFile.exists()) && legacyHarEvals(name, await evalFile.text()))
    warnings.push(
      `${name}: temporary exact-corpus exception for tags/pressure until the HAR branch migration lands; assertions remain required`,
    );
  if (data.description.length > 600)
    warnings.push(
      `${name}: description has ${data.description.length} characters (editorial target: 600); preserve routing boundaries when shortening`,
    );
  const trigger = data.description.indexOf("Use when");
  if (trigger > 300)
    warnings.push(
      `${name}: "Use when" starts after ${trigger} characters (editorial target: first 300)`,
    );
  return warnings;
}

export async function triggerOverlapWarnings(
  root: string,
  skills: string[],
): Promise<string[]> {
  const positives = new Map<string, Set<string>>();
  for (const name of skills) {
    const file = Bun.file(
      join(root, "skills", name, "evals", "trigger-evals.json"),
    );
    if (!(await file.exists())) continue;
    let cases: unknown;
    try {
      cases = await file.json();
    } catch {
      continue; // Validation reports malformed files.
    }
    if (!Array.isArray(cases)) continue;
    for (const item of cases) {
      if (
        !isRecord(item) ||
        item.should_trigger !== true ||
        typeof item.query !== "string"
      )
        continue;
      const query = normalizeQuery(item.query);
      if (!positives.has(query)) positives.set(query, new Set());
      positives.get(query)!.add(name);
    }
  }
  return [...positives]
    .filter(([, names]) => names.size > 1)
    .map(
      ([query, names]) =>
        `Trigger overlap: ${JSON.stringify(query)} is positive in ${[...names].join(", ")}; review whether collaboration is intended`,
    );
}

export function catalogSize(
  entries: { name: string; description: string; path: string }[],
) {
  const namesAndDescriptions = entries.reduce(
    (total, skill) => total + skill.name.length + skill.description.length,
    0,
  );
  const paths = entries.reduce((total, skill) => total + skill.path.length, 0);
  const rendered = entries
    .map(
      (skill) => `- ${skill.name}: ${skill.description} (file: ${skill.path})`,
    )
    .join("\n").length;
  return {
    namesAndDescriptions,
    paths,
    formatting: rendered - namesAndDescriptions - paths,
    rendered,
  };
}

if (import.meta.main) {
  const root = resolve(import.meta.dir, "..");
  const skillsDir = join(root, "skills");
  const directories = await skillDirectories(skillsDir);
  if (directories.length === 0) throw new Error("No skills found in skills/");
  const errors = (
    await Promise.all([
      ...directories.map((entry) => validateSkill(join(skillsDir, entry))),
      validateSkill(join(root, "templates", "skill-template")),
      validateRepository(root, directories),
    ])
  ).flat();
  const warnings = (
    await Promise.all(
      directories.map((entry) => skillWarnings(join(skillsDir, entry))),
    )
  ).flat();
  warnings.push(...(await triggerOverlapWarnings(root, directories)));
  for (const warning of warnings) console.warn(`Warning: ${warning}`);
  const catalog = [];
  for (const name of directories) {
    const { description } = await readFrontmatter(join(skillsDir, name));
    if (typeof description === "string")
      catalog.push({
        name,
        description,
        path: join(skillsDir, name, "SKILL.md"),
      });
  }
  const size = catalogSize(catalog);
  console.log(
    `Catalog advisory (this checkout only): ${size.namesAndDescriptions} name/description characters + ${size.paths} path characters + ${size.formatting} formatting characters = ${size.rendered} estimated rendered characters; host budgets and other installed skills vary.`,
  );
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
  } else
    console.log(`Validated ${directories.length} skill(s) and the template.`);
}
