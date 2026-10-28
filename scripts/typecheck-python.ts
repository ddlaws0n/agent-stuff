import { resolve } from "node:path";

export async function pythonTypecheckArgs(root: string): Promise<string[]> {
  const config = Bun.TOML.parse(
    await Bun.file(resolve(root, "ty.toml")).text(),
  );
  if (
    !("environment" in config) ||
    !config.environment ||
    typeof config.environment !== "object"
  )
    throw new Error("ty.toml needs an environment table");
  const paths: unknown =
    "extra-paths" in config.environment
      ? config.environment["extra-paths"]
      : [];
  if (
    !Array.isArray(paths) ||
    !paths.every((path: unknown): path is string => typeof path === "string")
  )
    throw new Error("ty.toml environment.extra-paths must be strings");
  // ty 0.0.93 gives PEP 723 scripts separate projects. Relative project paths
  // are not inherited, so pass absolute CLI paths derived from the same config.
  return [
    "uvx",
    "--from",
    "ty==0.0.93",
    "--with-requirements",
    resolve(root, "scripts/installed-skills/requirements.txt"),
    "ty",
    "check",
    ...paths.flatMap((path) => ["--extra-search-path", resolve(root, path)]),
    "skills",
    "eval/harness",
    "scripts",
  ];
}

if (import.meta.main) {
  const root = resolve(import.meta.dir, "..");
  const child = Bun.spawn(await pythonTypecheckArgs(root), {
    cwd: root,
    stdout: "inherit",
    stderr: "inherit",
  });
  process.exitCode = await child.exited;
}
