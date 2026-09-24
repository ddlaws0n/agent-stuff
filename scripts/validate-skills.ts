import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, isAbsolute, join, relative, resolve, sep } from "node:path";
import { parseDocument } from "yaml";

const NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SEMVER =
  /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function validateSkill(directory: string): string[] {
  const errors: string[] = [];
  const skillFile = join(directory, "SKILL.md");
  const name = basename(directory);
  if (!existsSync(skillFile)) return [`${name}: missing SKILL.md`];

  const text = readFileSync(skillFile, "utf8");
  const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/.exec(text);
  if (!frontmatter)
    return [`${name}: SKILL.md needs YAML frontmatter and a Markdown body`];

  const document = parseDocument(frontmatter[1], { uniqueKeys: true });
  for (const error of document.errors)
    errors.push(`${name}: invalid YAML: ${error.message}`);
  if (document.errors.length) return errors;
  const data: unknown = document.toJS();
  if (!isRecord(data)) return [`${name}: frontmatter must be a mapping`];

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
  if (!existsSync(join(directory, "LICENSE")))
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
  if (!frontmatter[2].trim()) errors.push(`${name}: SKILL.md body is empty`);

  const evalFile = join(directory, "evals", "evals.json");
  if (existsSync(evalFile)) {
    try {
      const evals: unknown = JSON.parse(readFileSync(evalFile, "utf8"));
      if (
        !isRecord(evals) ||
        evals.skill_name !== name ||
        !Array.isArray(evals.evals) ||
        evals.evals.length === 0
      ) {
        errors.push(
          `${name}: evals/evals.json needs matching skill_name and a nonempty evals array`,
        );
      } else {
        const ids = new Set<number>();
        for (const [index, item] of evals.evals.entries()) {
          const prefix = `${name}: eval ${index + 1}`;
          if (!isRecord(item)) {
            errors.push(`${prefix} must be an object`);
            continue;
          }
          if (
            !Number.isSafeInteger(item.id) ||
            (item.id as number) < 1 ||
            ids.has(item.id as number)
          ) {
            errors.push(`${prefix} needs a unique positive integer id`);
          } else ids.add(item.id as number);
          if (typeof item.prompt !== "string" || !item.prompt.trim())
            errors.push(`${prefix} needs a prompt`);
          if (
            typeof item.expected_output !== "string" ||
            !item.expected_output.trim()
          )
            errors.push(`${prefix} needs expected_output`);
          if (
            item.files !== undefined &&
            (!Array.isArray(item.files) ||
              item.files.some((file) => {
                if (typeof file !== "string" || !file || isAbsolute(file))
                  return true;
                const path = resolve(directory, file);
                const within = relative(directory, path);
                return (
                  within === ".." ||
                  within.startsWith(`..${sep}`) ||
                  !existsSync(path) ||
                  !statSync(path).isFile()
                );
              }))
          )
            errors.push(
              `${prefix} files must be existing paths within the skill`,
            );
          if (
            item.assertions !== undefined &&
            (!Array.isArray(item.assertions) ||
              item.assertions.some(
                (assertion) =>
                  typeof assertion !== "string" || !assertion.trim(),
              ))
          ) {
            errors.push(`${prefix} assertions must be nonempty strings`);
          }
        }
      }
    } catch (error) {
      errors.push(`${name}: invalid evals/evals.json: ${String(error)}`);
    }
  }
  return errors;
}

if (import.meta.main) {
  const skillsDir = resolve(import.meta.dir, "..", "skills");
  const directories = readdirSync(skillsDir, { withFileTypes: true }).filter(
    (entry) => entry.isDirectory() && !entry.name.startsWith("."),
  );
  if (directories.length === 0) throw new Error("No skills found in skills/");
  const errors = directories.flatMap((entry) =>
    validateSkill(join(skillsDir, entry.name)),
  );
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
  } else console.log(`Validated ${directories.length} skill(s).`);
}
