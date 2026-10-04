---
name: manage-environments-orbstack
description: >-
  Configures, migrates, and troubleshoots OrbStack on macOS: Docker engine and
  Compose, Linux machines, orb/orbctl commands, SSH editing, orb.local domains
  and HTTPS, volumes, backups, Docker Desktop migration, and isolated machines.
  Use when OrbStack, orb, orbctl, or orb.local is mentioned or the Docker
  context is orbstack. Do not use for Docker Desktop, Colima, Podman, or Docker
  on remote Linux hosts.
license: MIT
compatibility: >-
  Requires macOS with OrbStack installed and shell access.
metadata:
  author: ddlaws0n
  version: "0.1.0"
---

# OrbStack environments

Command syntax in this skill was checked against OrbStack 2.2.3 CLI help. Recheck `orbctl <command> --help` on other releases.

## Workflow

1. Identify the execution surface: macOS shell, OrbStack machine, Docker container, or remote host. Determine the named target, desired result, CPU architecture, and data that must persist. Inspect available state before asking for missing details.
2. On macOS, inspect `orb version`, `orb status`, and relevant subcommand help. For Docker tasks, inspect `docker context show`, `docker context ls`, and `docker info`. For machine tasks, inspect `orb list` and `orb info <machine>`. Run only checks relevant to the task; do not start services just to inspect them.
3. Prefer installed CLI help for syntax, official docs (docs.orbstack.dev) for behavior, and community posts for hypotheses. If they disagree, record the version and discrepancy. Check release notes for reported regressions.
4. Make the smallest relevant change. Preserve the original config and target explicitly; avoid silently changing the default machine, Docker context, or global platform preference.
5. Validate the user's actual workflow: correct daemon or machine, app health, intended network path, file changes, and required persistence. Report observed results separately from untested assumptions.

## References

- [references/commands.md](references/commands.md): read for machine provisioning, file transfer, settings, SSH, architecture/emulation, or Kubernetes.
- [references/networking.md](references/networking.md): read for connectivity, domains, TLS, LAN exposure, or VPN/proxy issues.
- [references/storage-diagnostics.md](references/storage-diagnostics.md): read for mounts, performance, backups, Docker Desktop migration, isolation, or failure diagnosis.

## Gotchas

- Use OrbStack's Docker engine for Compose/devcontainers. Use a Linux machine when a distro environment, system services, or SSH editing is required. Do not install a second Docker daemon in a machine unless the task requires it; first identify which daemon commands address.
- Pin a supported distro release and important image/tool versions for repeatable environments. Unqualified `ubuntu` selects OrbStack's current default, which can change.
- On Apple Silicon, prefer native ARM64. Scope AMD64 to the command or service that needs it; avoid globally exporting `DOCKER_DEFAULT_PLATFORM`.
- Bind-mount source edited on macOS; use named volumes for database data and high-churn dependencies/caches. For Linux-native development, keep code in the machine and edit over SSH. Measure representative work before changing the layout.
- Container domains provide automatic HTTPS through OrbStack's proxy. Do not promise that every Linux machine domain receives automatic TLS. Verify machine server ports and certificates separately.
- VM localhost forwarding and Docker port publication are different mechanisms. Domain/IP access also depends on OrbStack network settings and conflicts with VPN subnets.
- `docker.expose_ports_to_lan` and `machines.expose_ports_to_lan` default to `true`: a container port published without a host IP, or a machine listener on `0.0.0.0`, is reachable from the LAN. Bind published ports to `127.0.0.1` or disable the setting when access should stay on the Mac.
- Normal machines integrate with Mac files and forward the SSH agent. For unfamiliar code or autonomous agents, consider `--isolated`; add `--isolate-network` when peer access is unnecessary. These machines share a kernel with other OrbStack workloads and are not separate-kernel VMs.
- Never treat `orb reset`, `orb delete docker`, machine/cluster deletion, volume pruning, or `docker compose down -v` as routine repairs. Perform destructive work only within explicit authorization for the target and data loss; arrange a recoverable backup first when data matters.
- Get explicit user consent before running `orb reset -y`, `orb delete -f`, `orb delete --all`, or `orb doctor --fix`. These skip confirmation or change Docker integration state; show the command and its impact first.
- Do not copy host private keys or credential directories into images. Agent forwarding grants use of credentials; enable it deliberately for isolated machines and containers.

## Output

Return the target and relevant versions, change made and reason, checks performed and their results, and any remaining blocker. Include the exact access URL or SSH target when useful. If execution is unavailable, provide commands and expected results and state that they have not been run. Never claim a docs example or successful command exit proves application readiness.
