import { expect, test } from "bun:test";
import {
  chmod,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { buildDockerArgs, inspectEvent, parseArgs, runCell } from "./run";

test("requires an explicit OpenRouter model and a safe run name", () => {
  expect(
    parseArgs([
      "--run-name",
      "local-1",
      "--model",
      "openrouter/z-ai/glm-5.3-flash",
    ]),
  ).toEqual({
    runName: "local-1",
    model: "openrouter/z-ai/glm-5.3-flash",
  });
  expect(() =>
    parseArgs([
      "--run-name",
      "../escape",
      "--model",
      "openrouter/z-ai/glm-5.3-flash",
    ]),
  ).toThrow();
  expect(() =>
    parseArgs(["--run-name", "local-2", "--model", "openai-codex/gpt-6-luna"]),
  ).toThrow();
});

test("only the disposable fixture enters each Pi container", () => {
  const cell = {
    key: "case-with_skill",
    skill: "create-agentsmd",
    condition: "with_skill" as const,
    cwd: "/tmp/disposable/case",
    root: "/private/eval/results/case",
    task: "Inspect the fixture",
    model: "openrouter/z-ai/glm-5.3-flash:high",
  };
  const args = buildDockerArgs(cell).join(" ");
  expect(args).toContain("type=bind,src=/tmp/disposable/case,dst=/workspace");
  expect(args).toContain("--read-only");
  expect(args).toContain("--cap-drop ALL");
  expect(args).toContain("--no-extensions --no-skills --no-approve");
  expect(args).toContain("--skill /workspace/.agents/skills/create-agentsmd");
  expect(args).not.toContain(cell.root);
  expect(args).not.toContain("/repo/skills");
  expect(args).not.toContain("op://");
  expect(
    buildDockerArgs({ ...cell, condition: "without_skill" }).join(" "),
  ).not.toContain("--skill");
});

test("rejects resolved provider/model mismatches", () => {
  const message = {
    role: "assistant",
    provider: "openrouter",
    model: "z-ai/glm-5.3-flash",
    stopReason: "stop",
  };
  expect(
    inspectEvent(
      { type: "message_end", message },
      "openrouter/z-ai/glm-5.3-flash",
    ),
  ).toEqual(message);
  expect(() =>
    inspectEvent(
      { type: "message_end", message },
      "openrouter/openai/gpt-6-luna",
    ),
  ).toThrow();
  expect(
    inspectEvent(
      { type: "message_start", message },
      "openrouter/z-ai/glm-5.3-flash",
    ),
  ).toBeNull();
});

test("collects and redacts Pi JSON output without invoking a real model", async () => {
  const base = await mkdtemp(join(tmpdir(), "eval-runner-test-"));
  const originalKey = process.env.OPENROUTER_API_KEY;
  try {
    const bin = join(base, "bin");
    const cwd = join(base, "fixture");
    const root = join(base, "results");
    await mkdir(bin);
    await mkdir(cwd);
    await mkdir(join(root, "outputs"), { recursive: true });
    const message = {
      type: "message_end",
      message: {
        role: "assistant",
        provider: "openrouter",
        model: "z-ai/glm-5.3-flash",
        stopReason: "stop",
        content: [{ type: "text", text: "done fake-test-key" }],
        usage: { totalTokens: 5, cost: { total: 0.01 } },
      },
    };
    await writeFile(
      join(bin, "docker"),
      `#!/bin/sh\nprintf '%s\\n' '${JSON.stringify(message)}' '{"type":"agent_settled"}'\n`,
    );
    await chmod(join(bin, "docker"), 0o755);
    await writeFile(join(cwd, "AGENTS.md"), "Fixture mentions fake-test-key\n");
    process.env.OPENROUTER_API_KEY = "fake-test-key";
    await runCell(
      {
        key: "case-with_skill",
        skill: "create-agentsmd",
        condition: "with_skill",
        cwd,
        root,
        task: "Inspect fixture",
        model: "openrouter/z-ai/glm-5.3-flash:high",
      },
      "case-with_skill",
      join(bin, "docker"),
    );
    expect(await readFile(join(root, "outputs/final.md"), "utf8")).toContain(
      "[REDACTED]",
    );
    expect(await readFile(join(root, "outputs/AGENTS.md"), "utf8")).toContain(
      "[REDACTED]",
    );
    expect(
      await readFile(join(root, "transcript.jsonl"), "utf8"),
    ).not.toContain("fake-test-key");
    expect(
      JSON.parse(await readFile(join(root, "timing.json"), "utf8"))
        .total_tokens,
    ).toBe(5);
  } finally {
    if (originalKey === undefined) delete process.env.OPENROUTER_API_KEY;
    else process.env.OPENROUTER_API_KEY = originalKey;
    await rm(base, { recursive: true, force: true });
  }
});

test("terminates a child when resolved-model validation fails", async () => {
  const base = await mkdtemp(join(tmpdir(), "eval-runner-failure-"));
  try {
    const root = join(base, "results");
    await mkdir(root);
    const bin = join(base, "docker");
    const event = {
      type: "message_end",
      message: {
        role: "assistant",
        provider: "wrong-provider",
        model: "wrong-model",
      },
    };
    await writeFile(
      bin,
      `#!/usr/bin/env bun\nconsole.log(${JSON.stringify(JSON.stringify(event))});\nawait Bun.sleep(60_000);\n`,
    );
    await chmod(bin, 0o755);
    const started = Date.now();
    await expect(
      runCell(
        {
          key: "mismatch",
          skill: "create-agentsmd",
          condition: "without_skill",
          cwd: base,
          root,
          task: "fixture",
          model: "openrouter/z-ai/glm-5.3-flash:high",
        },
        "mismatch",
        bin,
      ),
    ).rejects.toThrow("Resolved model differs");
    expect(Date.now() - started).toBeLessThan(2000);
    expect(await Bun.file(join(root, "status.json")).exists()).toBe(false);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});
