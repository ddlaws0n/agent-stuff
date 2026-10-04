import { $ } from "bun";
import { access } from "node:fs/promises";
import { join, resolve } from "node:path";
import { skillDirectories } from "./validate-skills";

// Runs each skill's Python tests with that skill's own test requirements.
const root = resolve(import.meta.dir, "..");
let suites = 0;
for (const skill of await skillDirectories(join(root, "skills"))) {
  const tests = join("skills", skill, "tests");
  const hasTests = await access(join(root, tests)).then(
    () => true,
    () => false,
  );
  if (!hasTests) continue;
  const requirements = join(tests, "requirements.txt");
  const withRequirements = (await Bun.file(join(root, requirements)).exists())
    ? ["--with-requirements", requirements]
    : [];
  console.log(`${skill}:`);
  await $`uv run ${withRequirements} python -B -m unittest discover -s ${tests} -p ${"test_*.py"}`.cwd(
    root,
  );
  suites++;
}
console.log(`Ran ${suites} skill test suite(s).`);
