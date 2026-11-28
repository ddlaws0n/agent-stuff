# Herdr Hosts

Update this file when a host is added or retired, config management changes (for example, adopting chezmoi and which paths it syncs), backups move, or a host gets its own font, scaling, or editor overrides.

<!-- prettier-ignore -->
| Host | Platform | Config root | Config management |
|-|-|-|-|
| Primary Mac | macOS, Apple Silicon (`arm64`) | `$HOME/.config/herdr-app/` | Manual; not synced by chezmoi or another dotfile manager |

## Constraints

- Generated API docs (`AGENTS.md`, `*.d.ts`) match each host's installed Herdr version; read them on the target host.
- `mods/gitview/bin/herdr-gitview` is an Apple Silicon macOS build (`v0.6.0`). Copying the config to an Intel Mac or another OS requires a matching binary.
- The Trash patch needs `/usr/bin/trash`. Gitview editor integrations use `vim`; Neovim is not required.
- Pre-Zed backup: `$HOME/.config/herdr-app/.backups/pre-zed-PKQsJ56w/`, a read-only reference snapshot.
