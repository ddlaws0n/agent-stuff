# Storage, backup, and troubleshooting

## Choose storage deliberately

<!-- prettier-ignore -->
| Workload | Default | Reason |
|-|-|-|
| Source edited by Mac tools | Narrow source bind mount | Familiar editing and live changes |
| Database data | Named volume | Linux-side I/O and explicit persistence |
| Dependencies/build cache | Named volume when practical | Avoid many cross-filesystem operations |
| Linux-only workspace | Guest-native directory + SSH editor | Linux semantics and toolchain locality |

Name volumes explicitly and record their purpose. Keep Mac and Linux dependency installations separate, especially native modules. A dependency volume can become stale after lockfile changes; reinstall deliberately instead of deleting unrelated volumes. Validate UID/GID, permissions, case sensitivity, and file watching against the actual app.

Normal machine sharing exposes the Mac home path at the same absolute path inside the guest and again under the `/mnt/mac` prefix. Mac-side browsing is under the `OrbStack` folder in the Mac home directory (one subfolder per machine); Docker volumes appear in its `docker/volumes` subfolder. Attach named volumes by name, not by bind-mounting this browsing path. Inspect database contents through its tools; editing live database files through Finder can corrupt them. Do not assume `/mnt/machines/<name>` is a supported interface on every release; inspect before relying on it.

## Backup and migration

```sh
orb docker volume export my-volume my-volume.tar.zst
orb docker volume import my-volume.tar.zst
orb export myvm myvm.tar.zst
```

Confirm import behavior with local help before restoring into an existing name. For databases, prefer an application-consistent dump or quiesce writers before volume export. Machine export pauses the machine, but a restore drill is still necessary. Store backups outside disposable OrbStack data; a clone on the same storage is not an independent backup.

Migration procedure: inventory existing Docker contexts, containers, images, named volumes, bind paths, and architecture requirements; capture application-consistent backups; then run `orb docker migrate` (check `orb docker migrate --help` first) to copy containers, volumes, and images from Docker Desktop. Validate state and app behavior on a small project before cutting over the rest. Keep Docker Desktop and its data intact until verification. A context switch alone does not transfer data. Use `--force` only with consent when OrbStack already holds data. Older top-level `orb migrate` examples are outdated; the command lives under `orb docker`.

## Diagnose in this order

<!-- prettier-ignore -->
| Symptom | First checks | Targeted next step |
|-|-|-|
| Cannot connect to Docker | `orb status`, context, `DOCKER_HOST`/`DOCKER_CONTEXT` overrides, `docker info` | Select correct context explicitly; start engine only when required |
| App unreachable | App health, listener, network, port publication, DNS, TLS | Fix the failed layer and test again |
| Slow builds/watch failures | CPU architecture, `docker stats`, mount type, watch limits | Compare the same workload on Linux storage; isolate native dependencies |
| Machine fails to boot | `orb info myvm`, `orb logs myvm` | Match error and version to current docs/issues |
| Provisioning incomplete | cloud-init status and output log | Fix user-data or provisioning step; creation alone is insufficient |
| Memory pressure | Host pressure, workload usage, global and machine caps | Stop unused workloads or adjust justified limits |

Use `docker --context orbstack ...` to avoid changing the global context during a one-off check. `docker context use orbstack` is appropriate only when intentionally switching the user's default; environment overrides can supersede context choice.

`orb doctor` checks that OrbStack controls the Docker integration; `orb doctor --fix` changes that state, so run it only with user consent. `orb report` creates support diagnostics; inspect/redact before sharing and obtain authorization to upload. `orb logs myvm` provides boot logs. Check `orb logs --help` before assuming a Docker target is supported. `orb restart docker` interrupts workloads; explain the impact before using it where active work matters.

For isolation:

```sh
orb create --isolated --isolate-network ubuntu:noble sandbox
```

This removes default host integrations and peer/host network access while preserving internet access. If needed, add a narrow `--mount /path/to/project:/work`; forwarded agents are opt-in with `--forward-ssh-agent`. Verify the installed release supports these flags. For code actively attempting kernel escape, use a separate-kernel VM. Isolation does not imply an internet allowlist.
