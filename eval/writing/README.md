# Developing the writing skill

Install the `writing/` directory from `dist/writing.zip` in your agent's skill directory. The ZIP has one entrypoint, 21 writing guides, three optional detail sheets and the license notices. An installed copy needs a way to read Markdown. The importer and evaluator run only during development.

## Credits

Surendran B (`surendranb`) published the original 21 skills and three supplementary references under the MIT license. The upstream Git history also credits Claude Fable 5 and Claude Opus 5.5 in co-author trailers. ddlaws0n maintains the unified router, import adaptations, tests and packaging. Both copyright and permission notices travel in the ZIP. [Original collection](https://github.com/surendranb/writing-skills/tree/03bd5bb33e0760cf44c32822d2d79d7e2c42c6a6/skills) · [Upstream license](https://github.com/surendranb/writing-skills/blob/03bd5bb33e0760cf44c32822d2d79d7e2c42c6a6/LICENSE) · [Upstream history](https://github.com/surendranb/writing-skills/commits/03bd5bb33e0760cf44c32822d2d79d7e2c42c6a6/skills/)

The original guides also credit the methods they draw on, including Google’s SRE books, Wikipedia’s WikiProject AI Cleanup and _Smart Brevity_ (VandeHei, Allen and Schwartz, 2022). Those works informed the guides. The collection credit above identifies the source of the files imported here.

## Rebuild from source

Run these commands from the repository root with Git and uv. The source clone may be bare or have any working tree. The importer reads Git blobs at the pinned commit, even if the checkout is dirty or on another branch.

```sh
git clone --bare https://github.com/surendranb/writing-skills.git /tmp/writing-upstream.git
uv run eval/writing/build.py import /tmp/writing-upstream.git
uv run eval/writing/build.py check /tmp/writing-upstream.git
uv run eval/writing/build.py package /tmp/writing-upstream.git
bun run check
bunx skills add . --list
```

The source inventory must match all 24 reviewed paths. For each guide the importer strips its standalone frontmatter. It removes 20 identical instructions to invoke a separate editing skill because the router already includes a naturalness pass. Three links now point to sibling detail sheets, whose bytes match upstream. Six exact edits adapt the naturalness guide's vocabulary and precedence checks to a single skill. Each replacement must match once. The combined LICENSE preserves both projects' notices and names the source revision. To update upstream, review the source diff, inventory and transformation rules before changing the pin. [Pinned upstream](https://github.com/surendranb/writing-skills/tree/03bd5bb33e0760cf44c32822d2d79d7e2c42c6a6)

`check` detects missing or extra references, source drift, bad router metadata, broken links and unresolved upstream invocations. `package` runs that check and verifies a ZIP round trip before publishing the file. Entries have sorted paths, fixed timestamps and permissions, and stored bytes. Repo-required eval fixtures stay in the source tree and the ZIP allowlist excludes them. Run `uv run -m unittest discover -s eval/writing` and `bun test eval/writing/fixture-reads.test.mjs` for the fast local regression checks.

## Run the comparisons

The three conditions expose an empty catalog, the original 21 skill directories, or the runtime contents of the ZIP. Each cell gets a fresh process and a temporary directory. Pi performs its own discovery. Only the request and its inline synthetic source notes go to the writer. The judge sees the same request, the criteria and three anonymously labelled drafts in a seeded order. It has no skill or tools. The developer adapter uses Pi 1.6.0 and an authenticated model. All conditions in a comparison use the same model and thinking setting. Each call has a 120-second timeout.

```sh
uv run eval/writing/evaluate.py /tmp/writing-upstream.git --model openai-codex/gpt-6.2-sol \
  --out eval/results/writing/smoke --cases q1,q3,q11 --judge --reverse
uv run eval/writing/evaluate.py /tmp/writing-upstream.git --model openai-codex/gpt-6.2-sol \
  --out eval/results/writing/triggers --suite activation --variants unified
uv run eval/writing/evaluate.py /tmp/writing-upstream.git --model openai-codex/gpt-6.2-sol \
  --out eval/results/writing/routes --suite routing --variants unified
uv run eval/writing/evaluate.py report eval/results/writing/smoke
```

With no case or suite selected, the default is a three-case smoke run. Use a **new** output directory for each run. Before widening the suite, use `--cases`, `--split dev` or `--split held-out` to bound it. The full quality suite takes 36 writing calls and 12 judge calls with `--suite quality --judge`. Reversing draft order adds one judge call per case. Errors stop the batch, preserve completed cells and appear as evaluation errors, outside the quality scores.

- **Activation** uses 10 positive requests and 10 near misses, including six held out before running. A successful read of the entrypoint counts as activation.
- **Routing** uses the 12 quality cases plus ten focused cases. Together they exercise all 21 guides and all supplements. The first main guide, required and permitted files, and the read budget are separate assertions. A detail sheet can finish loading before its main guide. Reads are counted from paired tool events with a successful text result. A mention in the response earns no credit.
- **Quality** combines literal-preservation and length checks with a source-grounded blind rubric for fidelity, usefulness, format and voice. A material failure loses to a clean draft regardless of numeric score. The report counts each case once and combines order-reversed votes where available. Inspect blind packets and judge reasons for human review.
- **Frozen controls** let a router-only change reuse the same no-skill and upstream drafts. Add `--controls eval/results/writing/previous-run` to a three-way comparison. The runner checks the model, Pi version, upstream pin, fixture and guard hashes, and the identity of every control cell. It records source checksums and grades the new drafts blind alongside the exact saved controls.
- **Evidence** lives in the ignored `eval/results/writing/` tree. Each cell records output, model, elapsed time, successful file paths, read lengths and hashes, usage and deterministic checks. Usage is summed over assistant turns, including tool use. Missing counters stay null. Reported cost is the model adapter's estimate. The report regrades saved observations without another model call and records both scoring fingerprints where available. It also reports all successful file reads, with the router included, and the paired first-turn input overhead against no skill.

The writer can read only installed fixture files. The adapter disables implicit extensions, global skills, project instructions, MCP, saved sessions and prompt templates. A small Pi hook checks read targets before opening them. The grader gets no tools. Keep the corpus and answer keys outside the model's workspace. Developer instructions follow the [Agent Skills specification](https://agentskills.io/specification), [authoring guidance](https://agentskills.io/skill-creation/best-practices), [activation guidance](https://agentskills.io/skill-creation/optimizing-descriptions) and [output evaluation guide](https://agentskills.io/skill-creation/evaluating-skills).

## Measured results

On 27 November 2026 the main run used Pi 1.6.0 and `openai-codex/gpt-6.2-sol` at low thinking. It covered all 42 fixtures. Four quality cases, four focused routes and six activation cases were designated held out before running. Quality comparisons used fresh unified drafts and new blind grades alongside matched controls from the preceding run. The table sums provider-reported tokens over all turns of the 12 writing tasks, excluding judges.

<!-- prettier-ignore -->
| Condition | Mechanical checks | Total tokens | Median elapsed | Median successful file reads |
|-|-|-|-|-|
| No skill | 39/40 | 9,922 | 5.31 s | 0 |
| Original 21 skills | 39/40 | 149,230 | 9.99 s | 2 |
| Unified writing | 40/40 | 74,497 | 10.11 s | 2 (entrypoint and one guide) |

- **Discovery and routing.** The final skill opened for all ten writing requests and stayed closed for all ten near misses. All six held-out activation decisions were correct. It met every routing constraint on 10/10 focused routes and 10/12 quality cases. In one naturalness edit it stopped after reading the router. For a customer letter it chose plain language where the fixture required business writing. Overall primary selection was 20/22 (90.9%). The paired median first-turn input overhead above no skill was 207 tokens for unified and 3,106 for upstream. Consolidation reduced total writer tokens by 50.1% against upstream. Median latency was similar.
- **Blind quality.** Against no skill the unified drafts won four, tied four and lost four. Against upstream they won three, tied seven and lost two. The judge flagged no material failures in the 12 unified drafts. On the four held-out quality cases it preferred no skill three times and tied once. It preferred upstream once and tied three times. These observations fall short of the proposed 70% no-skill preference and 95% primary-routing targets.
- **Changes the results justified.** In the first 12-case run, both the locker proposal and the incident review added a claim unsupported by the notes. Asking the writer to trace claims back to the notes removed those two errors in the next run. One news draft then moved a period inside an exact quotation. A character-for-character comparison restored the period in the final suite and in a separate order-reversed check. We retained the original discovery description after an alternative produced identical activation decisions on all six smaller-model development prompts.
- **Portability.** The smaller `openai-codex/gpt-6-luna` pilot opened the unified skill on 0/3 quality cases. On the final two-case `openrouter/z-ai/glm-5.3-flash` comparison, the unified drafts passed 7/7 mechanical checks. GLM opened the incident guide and skipped the requested Yoda guide. Reversing judge order on those two cases yielded one tie and one loss against no skill, and one win and one loss against upstream.
- **Evidence and limits.** The full run series used 250 completed live model calls. The provider-reported estimate across writers and judges was $1.81, excluding reused controls. Inspect `eval/results/writing/final/`, `final-activation/`, `final-routing/`, `final-glm/` and `quote-verification/` under that evidence root. Each blind packet contains only the prompt, criteria and anonymous drafts. One observation per main case and a same-model judge limit generalization. Independent human preference grading and repeated full-suite trials remain unrun.

During the final run the formatter changed the italics delimiter around the credited upstream project name. The rendered credit and writing instructions were identical. Read-event checksums distinguish the two spellings. The runner now snapshots the runtime files at startup, and the separate quotation check ran from the final attached worktree. Early comparison runs used Pi’s read-only tool and audited its paths after execution. Subsequent runs also enforced the fixture boundary before reads.

The repository checks, official Agent Skills validator, extracted-archive validation, byte-for-byte rebuild and discovery listing all passed. The archive contains 26 files and occupies 96,312 bytes. SHA-256 `31997a5d68b1ffe890631cab25491828f45bdc5c18bdc0cc148f58ba3940264a`.
