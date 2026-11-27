import { expect, test } from "bun:test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import fixtureReads from "./fixture-reads.mjs";

test("the read tool can open an installed guide and cannot open the evaluator", () => {
  const cwd = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
  let guard;
  fixtureReads({ on: (_, handler) => (guard = handler) });
  const read = (path) => guard({ toolName: "read", input: { path } }, { cwd });
  expect(read("skills/writing/SKILL.md")).toBeUndefined();
  expect(read("skills/../eval/writing/evaluate.py").block).toBe(true);
  expect(read("missing").block).toBe(true);
});
