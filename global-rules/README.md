# Global agent instructions

Edit `global.md` and the corresponding agent’s Markdown tail here. From the repository root, preview, deploy, and check for drift with Bun.

```sh
bun scripts/render-global-rules.ts --dry-run
bun scripts/render-global-rules.ts
bun scripts/render-global-rules.ts --check
```

The renderer deploys the shared file under `~/.config/agent-rules/` so Claude Code and agy imports survive worktree or branch changes. Codex and both Pi homes receive the shared text plus their own tail. Orca mirrors the default Codex home’s instructions on launch. The renderer links that file to the shell Codex home and backs up changed files beside their originals before replacing them.

A full Codex dotfiles install can relink the shell home’s AGENTS.md to that repository. The renderer detects symlink drift even when the text matches. Reapply after a dotfiles install. Replacing the link leaves the tracked original intact.
