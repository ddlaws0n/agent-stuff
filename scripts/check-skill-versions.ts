import { $ } from "bun";

// Changes under these skill directories don't alter installed behavior.
const DEV_ONLY = new Set(["evals", "tests"]);
const VERSION = /^metadata:\n(?:\s+.*\n)*?\s+version:\s*"([^"]+)"/m;

export function changedSkills(paths: string[]): string[] {
  const skills = new Set<string>();
  for (const path of paths) {
    const [root, skill, entry] = path.split("/");
    if (root === "skills" && skill && entry && !DEV_ONLY.has(entry))
      skills.add(skill);
  }
  return [...skills].toSorted();
}

export function versionError(
  skill: string,
  before: string | undefined,
  after: string | undefined,
): string | undefined {
  if (!after) return undefined; // deleted, or the validator reports it
  if (!before) return undefined; // new or renamed skill
  if (Bun.semver.order(after, before) <= 0)
    return `${skill}: changed since base but version ${after} is not greater than ${before}`;
  return undefined;
}

async function versionAt(
  ref: string,
  skill: string,
): Promise<string | undefined> {
  const path = `skills/${skill}/SKILL.md`;
  const text = ref
    ? await $`git show ${ref}:${path}`.quiet().then(
        (result) => result.stdout.toString(),
        () => undefined,
      )
    : await Bun.file(path)
        .text()
        .catch(() => undefined);
  return text && VERSION.exec(text)?.[1];
}

if (import.meta.main) {
  // Fall back to the local main branch in clones without an origin remote.
  const hasOrigin =
    (await $`git rev-parse --verify --quiet origin/main`.quiet().nothrow())
      .exitCode === 0;
  const base = process.env.BASE_REF ?? (hasOrigin ? "origin/main" : "main");
  const mergeBase = (await $`git merge-base ${base} HEAD`.quiet()).stdout
    .toString()
    .trim();
  // Compare the working tree, so uncommitted and untracked changes count too.
  const tracked = (
    await $`git diff --name-only ${mergeBase}`.quiet()
  ).stdout.toString();
  const untracked = (
    await $`git ls-files --others --exclude-standard skills`.quiet()
  ).stdout.toString();
  const skills = changedSkills(`${tracked}\n${untracked}`.split("\n"));
  const errors: string[] = [];
  for (const skill of skills) {
    const error = versionError(
      skill,
      await versionAt(mergeBase, skill),
      await versionAt("", skill),
    );
    if (error) errors.push(error);
  }
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
  } else console.log(`Checked versions of ${skills.length} changed skill(s).`);
}
