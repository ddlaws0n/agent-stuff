import {
  chmodSync,
  copyFileSync,
  constants,
  lstatSync,
  mkdirSync,
  readFileSync,
  readlinkSync,
  renameSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

const sources = join(import.meta.dir, "../agent-rules");
const source = (name: string) =>
  readFileSync(join(sources, name + ".md"), "utf8").trimEnd();
const shared = source("global");
const combine = (base: string, tail: string) =>
  [base, source(tail)].filter(Boolean).join("\n\n") + "\n";

type Entry = { path: string; content: string; link?: boolean };

export function plan(home: string): Entry[] {
  const stable = join(home, ".config/agent-rules/global.md");
  const codex = join(home, ".config/codex/AGENTS.md");
  const pi = combine(shared, "pi");
  return [
    { path: stable, content: shared + "\n" },
    {
      path: join(home, ".claude/CLAUDE.md"),
      content: combine("@" + stable, "claude"),
    },
    {
      path: join(home, ".gemini/GEMINI.md"),
      content: combine("@[Shared global rules](" + stable + ")", "agy"),
    },
    { path: codex, content: combine(shared, "codex") },
    { path: join(home, ".codex/AGENTS.md"), content: codex, link: true },
    { path: join(home, ".config/pi/agent/AGENTS.md"), content: pi },
    { path: join(home, ".pi/agent/AGENTS.md"), content: pi },
  ];
}

export function render(home: string, mode: "check" | "dry-run" | "apply") {
  const changes = plan(home).filter(({ path, link, content }) => {
    const stat = lstatSync(path, { throwIfNoEntry: false });
    if (!stat) return true;
    if (stat.isSymbolicLink()) return !link || readlinkSync(path) !== content;
    if (!stat.isFile()) throw new Error("Expected a file at " + path);
    return link || readFileSync(path, "utf8") !== content;
  });
  for (const { path, content, link } of changes)
    console.log(link ? `link ${path} -> ${content}` : `write ${path}`);
  if (mode !== "apply") return changes.length;

  const stamp =
    new Date().toISOString().replaceAll(":", "-") + "-" + crypto.randomUUID();
  for (const { path } of changes) {
    const stat = lstatSync(path, { throwIfNoEntry: false });
    if (!stat) continue;
    const backup = path + "." + stamp + ".bak";
    if (stat.isSymbolicLink()) symlinkSync(readlinkSync(path), backup);
    else copyFileSync(path, backup, constants.COPYFILE_EXCL);
    console.log("backup " + backup);
  }
  for (const { path, content, link } of changes) {
    mkdirSync(dirname(path), { recursive: true });
    const temporary = path + "." + stamp + ".tmp";
    try {
      if (link) symlinkSync(content, temporary);
      else {
        writeFileSync(temporary, content, { flag: "wx", mode: 0o600 });
        const stat = lstatSync(path, { throwIfNoEntry: false });
        if (stat?.isFile()) chmodSync(temporary, stat.mode & 0o777);
      }
      renameSync(temporary, path);
    } finally {
      rmSync(temporary, { force: true });
    }
  }
  return changes.length;
}

if (import.meta.main) {
  const args = process.argv.slice(2);
  if (
    args.length > 1 ||
    (args.length && !["--check", "--dry-run"].includes(args[0]))
  ) {
    throw new Error(
      "Usage: bun scripts/render-agent-rules.ts [--check | --dry-run]",
    );
  }
  const mode =
    args[0] === "--check"
      ? "check"
      : args[0] === "--dry-run"
        ? "dry-run"
        : "apply";
  if (render(homedir(), mode) && mode === "check") process.exitCode = 1;
}
