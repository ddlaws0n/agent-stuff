import { $ } from "bun";
import { access } from "node:fs/promises";
import { join, resolve } from "node:path";
import {
  isPythonEntryPoint,
  pythonMinimum,
  readFrontmatter,
  skillDirectories,
} from "./validate-skills";

// Runs each skill's Python tests with that skill's own test requirements.
const root = resolve(import.meta.dir, "..");
const minimum = process.argv.includes("--minimum");
process.env.PYTHONDONTWRITEBYTECODE = "1";
let suites = 0;
for (const skill of await skillDirectories(join(root, "skills"))) {
  const directory = join(root, "skills", skill);
  const version = pythonMinimum(
    (await readFrontmatter(directory)).compatibility,
  );
  const python = minimum && version ? ["--python", version] : [];
  if (minimum) {
    const scripts = [
      ...new Bun.Glob("scripts/**/*.py").scanSync({ cwd: directory }),
    ];
    for (const script of scripts) {
      if (!isPythonEntryPoint(await Bun.file(join(directory, script)).text()))
        continue;
      if (!version)
        throw new Error(`${skill}: declare a Python minimum in compatibility`);
      console.log(`${skill}/${script}: Python ${version}`);
      // Load entry point syntax/imports with its declared PEP 723 dependencies.
      await $`uv run ${python} ${join(directory, script)} --help`.quiet();
    }
  }
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
  await $`uv run --no-project ${python} ${withRequirements} python -B scripts/run-python-tests.py ${tests}`.cwd(
    root,
  );
  suites++;
}
console.log(`Ran ${suites} skill test suite(s).`);
