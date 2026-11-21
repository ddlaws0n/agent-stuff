import { $ } from "bun";
import { chmod, mkdtemp, readdir, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { skillDirectories } from "./validate-skills";

const root = resolve(import.meta.dir, "..");
const sandbox = await mkdtemp(join(tmpdir(), "agent-skills-installed-"));
const checks = join(root, "scripts", "installed-skills");
const image = "agent-stuff-installed-skills:local";
try {
  await $`bunx --yes skills@1.7.0 add ${root} --skill ${"*"} --agent codex --copy --yes`
    .cwd(sandbox)
    .quiet();
  const installed = join(sandbox, ".agents", "skills");
  const skills = await skillDirectories(join(root, "skills"));
  for (const skill of skills) {
    const source = join(root, "skills", skill);
    const paths = ["SKILL.md", "LICENSE"];
    for (const directory of ["assets", "references", "scripts"]) {
      const entries = await readdir(join(source, directory), {
        recursive: true,
        withFileTypes: true,
      }).catch(() => []);
      for (const entry of entries) {
        if (entry.isFile() && !entry.parentPath.includes("__pycache__")) {
          paths.push(
            join(
              directory,
              entry.parentPath.slice(join(source, directory).length),
              entry.name,
            ),
          );
        }
      }
    }
    for (const path of paths) {
      const before = await Bun.file(join(source, path)).bytes();
      const after = await Bun.file(join(installed, skill, path)).bytes();
      if (!Buffer.from(before).equals(Buffer.from(after))) {
        throw new Error(`Installed file differs: ${skill}/${path}`);
      }
      if (/^scripts\/.*\.(py|sh)$/.test(path)) {
        const copied = join(installed, skill, path);
        await chmod(copied, (await stat(copied)).mode & ~0o111);
      }
    }
  }
  console.log(`Verified installed files for ${skills.length} skills.`);
  await $`docker build --tag ${image} ${checks}`;
  // Only installed skills and this check harness are mounted; no repository or credentials.
  // The writable fixture directory permits mock CLI execution. Installed files
  // remain read-only and have already had all executable bits removed.
  await $`docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --user 65534:65534 --tmpfs /tmp:rw,nosuid,nodev,exec,size=128m --mount ${`type=bind,src=${installed},dst=/skills,readonly`} --mount ${`type=bind,src=${checks},dst=/checks,readonly`} --workdir /tmp ${image} python -B /checks/verify.py`;
} finally {
  await rm(sandbox, { recursive: true, force: true });
}
