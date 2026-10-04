# Networking decision guide

<!-- prettier-ignore -->
| Direction or endpoint | Preferred path | Check |
|-|-|-|
| Mac → machine server | `localhost:<port>` or `<machine>.orb.local:<port>` | Guest listener, collision, exposure setting |
| Machine → Mac | `host.orb.internal:<port>` | Host bind address and firewall; guest localhost is guest-local |
| Mac → Docker app | `<container>.orb.local` or `<service>.<project>.orb.local` | Domain/IP access enabled and app listening |
| Container → Mac | `host.docker.internal:<port>` | Host listener and firewall |
| Compose service → service | Compose service name and container port | Same Docker network; do not use published host port |

Machines automatically forward server ports to macOS. A listener on `0.0.0.0` or `::` can also be reachable on the LAN; inspect `machines.expose_ports_to_lan` and disable it if access should stay on the Mac. Concurrent machines/apps can contend for a localhost port; use explicit machine domains/IPs and verify the responder.

Container domain HTTP ports are detected automatically. If detection chooses the wrong listener, use `dev.orbstack.http-port=3000`. Custom `dev.orbstack.domains` values can be comma-separated or wildcards, but only `.local` domains are supported. Compose project naming affects the generated hostname; use a stable project name if URLs must be stable. For databases, include the port, e.g. `database.demo.orb.local:5432`.

For cross-runtime compatibility or when domain access is unavailable, publish the required container port explicitly. Bind published ports to `127.0.0.1` when Mac-only access is intended. A typical container app must listen on `0.0.0.0` internally for bridge-network access.

## TLS

Automatic container HTTPS uses an OrbStack local CA and reverse proxy. Initial use can request CA installation. OrbStack also injects its CA into containers; `dev.orbstack.add-ca-certificates=false` disables injection. Custom language trust stores may still need configuration. Verify trust using the actual client; do not make `curl -k` or disabled TLS verification the fix.

For Linux machines, configure the web server independently. Documented routing settings include `machine.myvm.http_port` and `machine.myvm.https_port` for nonstandard ports. These are not evidence of automatic certificate issuance for a machine.

## VPN/proxy diagnosis

1. Compare the same hostname and endpoint from macOS and the failing guest/container. Separate DNS resolution, TCP reachability, and TLS trust.
2. Inspect Network settings and `network_bridge`. A detected subnet conflict can disable direct domain/IP access while published localhost ports remain useful.
3. Check Docker subnet overlap with corporate/VPN routes before changing address pools. Machine address ranges cannot be changed through the documented setting.
4. Check system proxy versus `network_proxy`, split DNS, macOS permissions, and exact release. Use an approved VPN-off comparison only if permitted; do not change corporate DNS or disable a VPN as the permanent fix.
5. Apply one evidence-backed change and repeat the original test. Restart only the affected component when needed.

VPN compatibility is a design goal, not a guarantee for every VPN client. Community DNS and routing reports identify useful reproduction cases; verify whether an issue applies to the installed version before adopting its workaround.
