import { basename, isAbsolute, join, relative, resolve, sep } from "node:path";
import { parseDocument } from "yaml";

const NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SEMVER =
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function validateMetadata(
  data: Record<string, unknown>,
  name: string,
  body: string,
  directory: string,
): Promise<string[]> {
  const errors: string[] = [];
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
  }
  if (data.license !== "MIT") errors.push(`${name}: license must be MIT`);
  if (!(await Bun.file(join(directory, "LICENSE")).exists()))
    errors.push(`${name}: missing bundled LICENSE`);
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
    Object.values(data.metadata).some((value) => typeof value !== "string")
  ) {
    errors.push(`${name}: metadata values must be strings`);
  }
  if (!body.trim()) errors.push(`${name}: SKILL.md body is empty`);
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
  if (!(await evalFile.exists())) return [];

  const errors: string[] = [];
  try {
    const evals: unknown = await evalFile.json();
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
        item.assertions !== undefined &&
        (!Array.isArray(item.assertions) ||
          item.assertions.some(
            (assertion: unknown) =>
              typeof assertion !== "string" || !assertion.trim(),
          ))
      ) {
        errors.push(`${prefix} assertions must be nonempty strings`);
      }
    }
  } catch (error) {
    errors.push(`${name}: invalid evals/evals.json: ${String(error)}`);
  }
  return errors;
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

  const errors = await validateMetadata(data, name, frontmatter[2], directory);
  errors.push(...(await validateEvals(directory, name)));
  return errors;
}

if (import.meta.main) {
  const skillsDir = resolve(import.meta.dir, "..", "skills");
  const directories: string[] = [];
  for await (const entry of new Bun.Glob("*").scan({
    cwd: skillsDir,
    onlyFiles: false,
  })) {
    if ((await Bun.file(join(skillsDir, entry)).stat()).isDirectory())
      directories.push(entry);
  }
  directories.sort();
  if (directories.length === 0) throw new Error("No skills found in skills/");
  const errors = (
    await Promise.all(
      directories.map((entry) => validateSkill(join(skillsDir, entry))),
    )
  ).flat();
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
  } else console.log(`Validated ${directories.length} skill(s).`);
}
