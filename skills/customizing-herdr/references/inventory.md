# Herdr Customization Inventory

Live state under `$HOME/.config/herdr-app/`. Update this file in the same session as any change: upstream pins, added or patched files, keybindings, layout block IDs, text sizes, and backup paths.

## Zed layout + Tokyo Night

- **Source:** [herdr-zed-layout @ `da95f40`](https://github.com/dantech99/herdr-zed-layout/tree/da95f40e180eab9b0c5b0a8edf5e650dc8d29d63), the active layout and theme.
- **Files:** `layouts/zed.json`, `layouts/zed.svg`, `themes/tokyo-night.json`, `mods/zed-*` (title and tabs, project commands, new-space dialog, sidebar footer, layout settings, Files tree and read-only file tabs, panel toggles).
- `zed-changes` and `zed-diff` are installed but unused by the `zed` layout; keep them for rollback.
- `zed-quota` and `quota-axi` are not installed. Leave the quota block out unless provider polling is requested.

## Files → Move to Trash (local patch)

- **Files:** `mods/zed-file-icons/main.js`, `mods/zed-file-icons/menu.js`.
- In local Mac spaces, right-clicking a row offers Move to Trash via `/usr/bin/trash` after confirmation. Remote and non-Mac spaces offer copy actions only.

## Gitview Changes panel

- **Source:** [herdr-gitview `v0.6.0`](https://github.com/ChmaraX/herdr-gitview/releases/tag/v0.6.0) Apple Silicon desktop bundle, not the TUI plugin.
- **Files:** `mods/gitview*`; the helper binary is `mods/gitview/bin/herdr-gitview`, configured by `mods/gitview/config.json`.
- **Layout contract:** keep block ID `changes` with `props.replaces` set to `zed-changes`, so rolling back to Zed's panel stays simple.
- **Keybindings:** `⌘⇧G` toggles the Changes panel in the `zed` layout; `⌘G` toggles a Gitview tab globally.
- Gitview runs Git, Herdr, and editor (Vim) commands and keeps local traces by default. It replaced `zed-changes`, which also had Git sync controls and `gh` PR lookups.

## Text size

- `layouts/zed.json`: JetBrains Mono at **13 px** for terminals; Geist for the UI.
- `settings.json`: **11 px** default for layouts without an override, including stock `main`.

## Installation and rollback

- Both bundles are real files, not installer-managed. Stage updates in a temporary directory, diff against the local patch, and run `herdr-app check` before moving files into place.
- Pre-install keybindings and settings are in `.backups/pre-zed-PKQsJ56w/`.
