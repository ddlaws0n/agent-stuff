#!/usr/bin/env bun
/** Orchestrate disposable Pi containers from the trusted host, without subagents. */
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

type Cell = {
  key: string;
  skill: string;
  condition: "with_skill" | "without_skill";
  cwd: string;
  root: string;
  task: string;
  model: string;
};
type Message = {
  role: string;
  content?: Array<{ type: string; text?: string }>;
  provider?: string;
  model?: string;
  stopReason?: string;
  usage?: { totalTokens?: number; cost?: { total?: number } };
};

const repo = join(import.meta.dir, "../..");
const harness = join(repo, "eval/harness");

export function parseArgs(args: string[]) {
  if (args.length !== 4 || args[0] !== "--run-name" || args[2] !== "--model") {
    throw new Error(
      "Usage: run.ts --run-name <new-name> --model <openrouter/model>",
    );
  }
  const [, runName, , model] = args;
  if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(runName))
    throw new Error("Invalid run name");
  if (
    !["openrouter/z-ai/glm-5.3-flash", "openrouter/openai/gpt-6-luna"].includes(
      model,
    )
  ) {
    throw new Error(
      "The container supports only the two pinned OpenRouter models",
    );
  }
  return { runName, model };
}

export function inspectEvent(
  event: { type?: string; message?: Message },
  expected: string,
) {
  if (event.type !== "message_end" || event.message?.role !== "assistant")
    return null;
  const message = event.message;
  const [provider, ...id] = expected.split("/");
  if (message.provider !== provider || message.model !== id.join("/")) {
    throw new Error(`Resolved model differs from requested ${expected}`);
  }
  return message;
}

export function buildDockerArgs(cell: Cell) {
  const skillPath = join("/workspace", ".agents/skills", cell.skill);
  const args = [
    "--mode",
    "json",
    "--no-session",
    "--no-extensions",
    "--no-skills",
    "--no-approve",
    "--offline",
    "--model",
    cell.model,
    ...(cell.condition === "with_skill" ? ["--skill", skillPath] : []),
    "--",
    cell.task,
  ];
  const dockerArgs = [
    "run",
    "--rm",
    "--init",
    "--read-only",
    "--tmpfs",
    "/tmp:rw,nosuid,size=2g",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--pids-limit",
    "256",
    "--memory",
    "4g",
    "--mount",
    `type=bind,src=${cell.cwd},dst=/workspace`,
    "--env",
    "OPENROUTER_API_KEY",
    "--env",
    "HOME=/tmp/eval-home",
    "--env",
    "PATH=/workspace/bin:/usr/local/bin:/usr/bin:/bin",
    "--env",
    "GH_CONFIG_DIR=/workspace/gh-config",
    "--env",
    "GH_MOCK_LOG=/workspace/gh-calls.jsonl",
    "--env",
    "GIT_TERMINAL_PROMPT=0",
    "--workdir",
    "/workspace",
    "agent-skills-eval:local",
    "pi",
    ...args,
  ];
  return dockerArgs;
}

export async function runCell(cell: Cell, key: string, dockerBin = "docker") {
  const expected = cell.model.replace(/:high$/, "");
  const startedAt = Date.now();
  const child = Bun.spawn([dockerBin, ...buildDockerArgs(cell)], {
    stdout: "pipe",
    stderr: "ignore",
  });
  const transcript = Bun.file(join(cell.root, "transcript.jsonl")).writer();
  let pending = "";
  const state: { settled: boolean; last: Message | null } = {
    settled: false,
    last: null,
  };
  let final = "";
  let tokens = 0;
  let cost = 0;
  let toolCount = 0;
  let turnCount = 0;
  const secret = process.env.OPENROUTER_API_KEY ?? "";
  const consume = (line: string) => {
    if (!line.trim()) return;
    const safe = secret ? line.replaceAll(secret, "[REDACTED]") : line;
    void transcript.write(`${safe}\n`);
    const event = JSON.parse(safe);
    const message = inspectEvent(event, expected);
    if (message) {
      state.last = message;
      tokens += message.usage?.totalTokens ?? 0;
      cost += message.usage?.cost?.total ?? 0;
      final =
        message.content
          ?.filter((part) => part.type === "text")
          .map((part) => part.text ?? "")
          .join("\n") ?? "";
    }
    if (event.type === "tool_execution_start") toolCount++;
    if (event.type === "turn_start") turnCount++;
    if (event.type === "agent_settled") state.settled = true;
  };
  try {
    const decoder = new TextDecoder();
    for await (const chunk of child.stdout) {
      pending += decoder.decode(chunk, { stream: true });
      let newline = pending.indexOf("\n");
      while (newline !== -1) {
        consume(pending.slice(0, newline).replace(/\r$/, ""));
        pending = pending.slice(newline + 1);
        newline = pending.indexOf("\n");
      }
    }
    pending += decoder.decode();
    if (pending) consume(pending);
  } catch (error) {
    child.kill();
    await child.exited;
    throw error;
  } finally {
    await transcript.end();
  }
  const exitCode = await child.exited;
  if (exitCode !== 0 || !state.settled || state.last?.stopReason !== "stop") {
    throw new Error(
      `${key}: Pi did not finish successfully (exit ${exitCode}); inspect the redacted transcript`,
    );
  }
  const endedAt = Date.now();
  const outputDir = join(cell.root, "outputs");
  await writeFile(join(outputDir, "final.md"), `${final}\n`);
  const workflowDir = join(cell.cwd, ".github/workflows");
  for (const source of [
    join(cell.cwd, "AGENTS.md"),
    ...(await readdir(workflowDir).catch(() => []))
      .filter((name) => /\.ya?ml$/.test(name))
      .map((name) => join(workflowDir, name)),
  ]) {
    if (!(await Bun.file(source).exists())) continue;
    const target = join(outputDir, source.slice(cell.cwd.length + 1));
    await mkdir(join(target, ".."), { recursive: true });
    const contents = await readFile(source, "utf8");
    const safeContents = secret
      ? contents.replaceAll(secret, "[REDACTED]")
      : contents;
    await writeFile(target, safeContents);
    if (/\.ya?ml$/.test(source))
      await writeFile(join(outputDir, "workflow.yml"), safeContents);
  }
  const status = {
    state: "complete",
    workflowKey: key,
    cwd: cell.cwd,
    startedAt,
    endedAt,
    steps: [{ model: cell.model }],
    toolCount,
    turnCount,
  };
  await writeFile(
    join(cell.root, "status.json"),
    `${JSON.stringify(status, null, 2)}\n`,
  );
  await writeFile(
    join(cell.root, "timing.json"),
    `${JSON.stringify(
      {
        total_tokens: tokens,
        duration_ms: endedAt - startedAt,
        total_duration_seconds: (endedAt - startedAt) / 1000,
        cost_usd: cost,
        model: cell.model,
        tool_calls: toolCount,
        turns: turnCount,
      },
      null,
      2,
    )}\n`,
  );
  console.log(
    `${key}: ${tokens} tokens, ${((endedAt - startedAt) / 1000).toFixed(1)}s`,
  );
}

async function main() {
  const { runName, model } = parseArgs(process.argv.slice(2));
  if (!process.env.OPENROUTER_API_KEY)
    throw new Error("OPENROUTER_API_KEY is required");
  const prepared = Bun.spawnSync(
    [
      "python3",
      "-B",
      join(harness, "prepare.py"),
      "--run-name",
      runName,
      "--model",
      model,
    ],
    {
      cwd: repo,
      stdout: "inherit",
      stderr: "inherit",
    },
  );
  if (prepared.exitCode !== 0) throw new Error("Preparation failed");
  const manifest: { cells: Cell[] } = JSON.parse(
    await readFile(
      join(repo, "eval/results", runName, "manifest.json"),
      "utf8",
    ),
  );
  for (const cell of manifest.cells) await runCell(cell, cell.key);
  const graded = Bun.spawnSync(
    ["python3", "-B", join(harness, "grade.py"), "--run-name", runName],
    {
      cwd: repo,
      stdout: "inherit",
      stderr: "inherit",
    },
  );
  if (graded.exitCode !== 0) throw new Error("Grading failed");
}

if (import.meta.main) {
  try {
    await main();
  } catch (error) {
    console.error(error instanceof Error ? error.message : "Eval failed");
    process.exitCode = 1;
  }
}
