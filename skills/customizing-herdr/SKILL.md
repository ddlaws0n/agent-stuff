---
name: customizing-herdr
description: >-
  Customizes and troubleshoots the Herdr desktop app (herdr-app) on macOS:
  layouts, themes, mods, keybindings, terminal text size, the Zed Files panel,
  and Gitview. Use when asked to configure, inspect, update, or debug Herdr
  desktop UI, even if only Zed layout or Gitview is mentioned. Not for the
  standalone herdr TUI or herdr-core (hc) terminal management.
license: MIT
compatibility: >-
  Requires macOS (Apple Silicon) with the Herdr desktop app (herdr-app)
  installed and shell access.
metadata:
  author: ddlaws0n
  version: "0.1.0"
---

# Customizing Herdr

`herdr-app` runs the desktop UI and hot-reloads its config from `$HOME/.config/herdr-app/`; `hc` is the separate terminal backend.

## Workflow

1. Read `$HOME/.config/herdr-app/AGENTS.md`, then `AGENTS.local.md` if present. Herdr regenerates `AGENTS.md`, `herdr.d.ts`, and `gpui-kit.d.ts` for the installed version: use them as the API reference and never edit them.
2. Read [references/inventory.md](references/inventory.md) and [references/hosts.md](references/hosts.md), run `herdr-app --version` and `herdr-app status`, then inspect the relevant live files, which win over the references when they differ.
3. Edit personal files only. Clone a shipped layout or mod before changing its structure or code, because updates overwrite originals. Never edit `layouts/.state/` or `view.json`.
4. For third-party mods or bundle updates: review the pinned source and disclose its subprocess, filesystem, and network access; stage it outside the live config and diff against local patches; add only free keybindings unless the user approves replacing one.
5. Validate: review each changed mod's `init()`, since `herdr-app check <mod-directory>` executes it, then run the check, read `herdr-app status` and any `*.error` files, and use `herdr-app shot "$TMPDIR/herdr-shot.png"` when the change is visual.
6. Update both reference files to match any change to layouts, themes, mods, patches, keybindings, text size, backups, hosts, or config management. If the skill directory is read-only, give the exact edits instead.

## References

- [references/inventory.md](references/inventory.md): installed layouts, mods, the Trash patch, keybindings, text sizes, and rollback.
- [references/hosts.md](references/hosts.md): host architecture, config management, backups, and binary or OS constraints.

## Gotchas

- Never run the upstream installers (`herdr-zed-layout`, `herdr-gitview`) over the live config: both bundles were installed by hand, and an installer can overwrite the Trash patch or patch the wrong layout.
- Preserve the Move to Trash patch in `mods/zed-file-icons/{main,menu}.js`; never restore upstream's permanent delete.
- Keep app-wide `zoom` at `1.0`. Change terminal text size in the active layout or `settings.json`, and confirm it with `herdr-app status`.
- Roll back with `herdr-app do layout.switch --name main`; mods and preferences stay. Copy single entries from backups, never whole files over newer settings.

## Output

Report the Herdr version and host, files changed and why, each validation run and its result, and whether the reference files were updated (or the pending edits).
