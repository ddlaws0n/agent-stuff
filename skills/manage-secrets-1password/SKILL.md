---
name: manage-secrets-1password
description: >-
  Operates on existing 1Password vaults with the op CLI. Use when a request
  needs direct 1Password access to list vaults, find items, read a field
  privately, create a login, or diagnose CLI authentication and approvals.
  Do not use for planning how to split vaults, designing access policies, or
  using the macOS Keychain or other secret stores. Ordinary Varlock runs and
  schema configuration belong to manage-secrets-varlock when available.
license: MIT
compatibility: >-
  Requires 1Password CLI v2 with access to the target account and vault.
  The metadata example uses jq.
metadata:
  author: ddlaws0n
  version: "0.2.2"
---

# 1Password vault and item operations

## Workflow

1. Identify the target account, vault, and operation. Prefer a scoped item list for discovery. Capture the list with tracing off and filter it only after a successful read. If the read fails, report that the vault could not be listed. Only a successful search can establish that there were no matches. For example, to find item titles containing “webhook”:

   ```bash
   items=$(op item list --vault Infra --format json 2>/dev/null) || exit "$?"
   printf '%s\n' "$items" | jq -r '.[] | select(.title | ascii_downcase | contains("webhook")) | [.id, .title] | @tsv'
   ```

2. For a new Login, let 1Password generate the password and suppress the item output. Check the exit status before reporting success. If a write's outcome is unclear, check the destination before attempting another create.

   ```bash
   op item create --category Login --vault Infra --title 'Webhook' --generate-password >/dev/null
   ```

3. For an existing secret, pipe the field directly from `op read` to a consumer that accepts stdin. When creating an item with supplied sensitive fields, stream a populated item JSON template from a trusted producer to `op item create --vault Infra - >/dev/null`. Keep values out of arguments, command tracing, logs, and temporary artifacts. Treat item JSON, selected fields, and creation output as sensitive even without `--reveal`.
4. Group related reads where practical. Before an interactive batch, tell the user which vault operations may prompt. Account, session, lock state, and authentication method affect the count.

## Diagnosing access

Check `op --version` locally. Use the failing operation's redacted error, the selected account, and the intended authentication method to narrow the cause. A failed `op whoami` means that invocation could not identify an authenticated account. It does not establish why. Desktop integration may need the app unlocked and CLI integration enabled. For a service account, check the target vault grant and whether the intended credential is configured without displaying it.

If another check would distinguish the causes, use one scoped read such as `op item list --vault Infra >/dev/null 2>&1`. Stop after an authorization failure and report the relevant next action. Avoid repeated probes that can trigger more approvals.

## Output

For a confirmed Login created with a generated password, use the actual item title and vault in this reply:

> Created the {title} Login in the {vault} vault. Open 1Password → {vault} → {title} to view the generated password.

Use the known location directly, without fetching the password for display. For a denied create, report the redacted error and next action. For an uncertain create, report what remains unconfirmed. For lookups, return the requested metadata.
