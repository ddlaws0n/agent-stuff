# Commands and development integration

Examples run from macOS unless marked otherwise. `myvm` is a placeholder; select an existing target before execution. Baseline: OrbStack 2.2.3 CLI help. Recheck flags on other releases.

## Machine lifecycle and execution

```sh
orb list
orb info myvm
orb create ubuntu:noble myvm
orb create --arch amd64 ubuntu:noble x86vm
orb create --memory 4G --cpus 2 --disk 64G ubuntu:noble dev
orb create ubuntu:noble provisioned -c cloud.yml
orb start myvm
orb stop myvm
orb restart myvm
orb default myvm                  # Changes implicit target
orb -m myvm                      # Interactive shell
orb -m myvm -u root id
orbctl run -m myvm -w project sh ./script.sh   # Guest-relative workdir; verify with pwd
```

`orb` handles management and guest execution; `orbctl` makes management explicit, and `orbctl run` makes execution explicit. The installed `run` command also has a `shell` alias. Do not infer working directory or path translation when running scripts: inspect paths and specify `-w`.

```sh
orb push -m myvm "$HOME/local.txt" /tmp/
orb pull -m myvm remote.txt ./
```

Pull sources are relative to the guest user's home; push destinations are relative to that home unless absolute. Avoid passing a tilde-prefixed source to `orb pull` in scripts: the Mac shell expands the tilde before OrbStack sees it. Prefer guest-relative or explicit guest paths.

Cloud-init: use `orb -m provisioned cloud-init status --long`; inspect `/var/log/cloud-init-output.log` on failure. Use `cloud-init status --wait` when supported and allow for an execution timeout. Machine creation is not proof provisioning succeeded. Keep secrets out of committed user data.

## Global settings versus per-machine limits

```sh
orb config show
orb config get memory_mib
orb config set memory_mib 8192
orb config set cpu 4
orb config set rosetta true
orb config set network_proxy auto
orb config docker
```

Global memory is a shared cap, not reserved RAM per machine. CLI CPU `4` represents a 400% cap; it is not a dedicated four-vCPU allocation. Change limits in response to observed pressure. Rosetta is normally worth leaving enabled. Proxy values include `auto`, `none`, or a supported proxy URL. `orb config docker` edits the Docker engine `docker.json` in OrbStack's config directory and restarts the engine when changed; plan for interruption. Save existing values before changes.

## SSH and macOS integration

```sh
ssh orb
ssh myvm@orb
ssh root@myvm@orb
ssh -G orb
```

OrbStack's generated SSH config connects to its common SSH endpoint. VS Code Remote SSH can use these targets. For clients that ignore OpenSSH config: host `localhost`, port `32222`, user `default` or `root@myvm`, key `id_ed25519` in the `ssh` folder of OrbStack's config directory (confirm with `ssh -G orb` or `orb ssh`). Inspect actual generated config instead of replacing it. Automatic guest agent forwarding is distinct from this login key; isolated machines disable forwarding by default. Keep the common SSH endpoint local unless remote access is explicitly required.

Inside a normal machine:

```sh
mac open https://example.com
mac notify "Build done"
```

From macOS, forward selected environment variables using `ORBENV=AWS_PROFILE:EDITOR orb -m myvm ./deploy.sh`. Forwarding a profile name does not provision its credentials. Review forwarded variables before handling sensitive workloads.

## Architecture and container agents

```sh
docker --context orbstack run --rm --platform linux/amd64 ubuntu:24.04 uname -m
```

Use per-service `platform: linux/amd64` only where needed. Emulation does not reproduce every native x86 kernel or hardware behavior. Diagnose binary architecture and interpreter availability before changing packages. The original Debian multiarch one-liner is not a general Rosetta repair; package changes depend on distro and failing binary.

OrbStack documents the Docker host-agent socket `/run/host-services/ssh-auth.sock`. To expose it deliberately, mount it as `/agent.sock` and set `SSH_AUTH_SOCK=/agent.sock`. Verify an agent exists and identities are loaded; do not bake private keys into the container.

## Kubernetes, only when requested

`orb start k8s`, `orb stop k8s`, and `orb restart k8s` manage the built-in cluster. Inspect `kubectl config current-context` before acting. Mac access supports service DNS such as `service.namespace.svc.cluster.local`, ClusterIP, NodePort, and LoadBalancer integration. LAN service access has a separate setting. No Ingress controller is installed by default. For local images, use a non-`latest` tag and appropriate pull policy. Do not install an old Ingress manifest copied from a docs example without checking its current supported release. Cluster deletion destroys state.
