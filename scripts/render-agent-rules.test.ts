import { expect, test } from "bun:test";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { plan, render } from "./render-agent-rules";

test("preview, migrate, back up and detect drift across both homes", () => {
  const home = mkdtempSync(join(tmpdir(), "agent-rules-"));
  try {
    const config = join(home, ".config/codex");
    mkdirSync(config, { recursive: true });
    const original = join(home, "tracked.md");
    writeFileSync(original, "original");
    symlinkSync(original, join(config, "AGENTS.md"));
    expect(render(home, "dry-run")).toBe(7);
    expect(render(home, "check")).toBe(7);
    expect(readdirSync(config)).toEqual(["AGENTS.md"]);
    expect(render(home, "apply")).toBe(7);
    const backup = readdirSync(config).find((name) => name.endsWith(".bak"))!;
    expect(readFileSync(join(config, backup), "utf8")).toBe("original");
    expect(readFileSync(original, "utf8")).toBe("original");
    for (const { path, content, link } of plan(home)) {
      expect(readFileSync(path, "utf8")).toBe(
        link ? readFileSync(content, "utf8") : content,
      );
    }
    expect(render(home, "apply")).toBe(0);
    expect(render(home, "check")).toBe(0);
    writeFileSync(join(home, ".pi/agent/AGENTS.md"), "drift");
    expect(render(home, "check")).toBe(1);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
