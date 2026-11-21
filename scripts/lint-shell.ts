import { $ } from "bun";
import { resolve } from "node:path";

const root = resolve(import.meta.dir, "..");
const files = (
  await $`git ls-files --cached --others --exclude-standard -z -- ${"*.sh"}`
    .cwd(root)
    .quiet()
).stdout
  .toString()
  .split("\0")
  .filter(Boolean);
for (const file of files) await $`bash -n ${file}`.cwd(root);
if (files.length)
  await $`uvx --from shellcheck-py==0.11.0.1 shellcheck ${files}`.cwd(root);
console.log(`Checked ${files.length} shell scripts with Bash and ShellCheck.`);
