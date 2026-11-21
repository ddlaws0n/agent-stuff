---
name: save-to-folio
description: >-
  Saves web articles to the Folio read-later app (savewithfolio.com) from the
  command line, logging in with credentials from 1Password and reusing a cached
  token. Use when the user asks to save, send, add, or queue a URL or article to
  Folio, or wants a reading list pushed into Folio. Do not use for Pocket,
  Instapaper, Readwise, browser bookmarks, or building offline EPUBs.
license: MIT
compatibility: >-
  Requires Python 3.11+ via uv, network access to api.savewithfolio.com, and
  the 1Password CLI (op) signed in with a Folio login item, or FOLIO_USERNAME
  and FOLIO_PASSWORD set.
metadata:
  author: ddlaws0n
  version: "0.2.3"
---

# Save to Folio

Folio has no public API. The bundled script calls the same private v4 endpoints as Folio's own web app and browser extension (checked against extension 1.1.1), so a change on their side can break it.

## Workflow

1. Collect the URLs. Only `http(s)` URLs are accepted. If the user describes articles instead of giving links, find the URLs first and confirm the list before saving.
2. Save them in one call, adding `--tag` only when the user names tags:
   ```bash
   uv run scripts/folio.py save https://example.com/a https://example.com/b --tag plane
   ```
3. Read the JSON lines. Each URL reports `ok`, plus `id` and `title` on success or `error` on failure. Exit code 1 means at least one URL failed.
4. Report known saves with failed tags separately (`saved: true`). Count those items as saved and name the tagging failure. Do not resubmit an unconfirmed or partially completed save.

## Scripts

`scripts/folio.py` (stdlib only):

<!-- prettier-ignore -->
| Command | Purpose |
|-|-|
| `uv run scripts/folio.py save URL... [--tag T]... [--dry-run]` | Save URLs; `--dry-run` prints the requests and sends nothing |
| `uv run scripts/folio.py check` | Verify the login works; logs in if no valid token is cached |
| `uv run scripts/folio.py logout` | Delete the cached token |

Authentication, in order:

1. Reuse the bearer token cached in `$XDG_CACHE_HOME/save-to-folio/token` (falls back to `.cache` in the home directory; file mode 0600).
2. On a missing token or an HTTP 401, log in once with `POST /v4/sessions`, cache the new token, and retry.
3. Credentials come from `FOLIO_USERNAME` / `FOLIO_PASSWORD` if set, otherwise `op read "$FOLIO_OP_ITEM/username"` and `/password`.

## Gotchas

- `op read` can show a 1Password approval prompt on the user's machine. If it fails, report the field reference and exit status.
- For a request to see the Folio service password, give one private inspection direction, then stop. If the user supplies `FOLIO_OP_ITEM`, name that vault and item. Otherwise say: “In 1Password, open the item configured by `FOLIO_OP_ITEM`. If you haven’t set it, the built-in default is `op://Private/Folio`. View its password field privately.” Never assume the actual vault or title. Skip secret reads, shell commands, and login troubleshooting.
- Never print, log, or echo the token or the password. Do not `cat` the token file.
- Folio fetches each URL on its own servers, so paywalled or login-only pages may save as a stub. Say so when a title comes back empty or generic.
- Saving is a live write to the user's account. Use `--dry-run` to test or demonstrate the script.

## Output

One line per URL: the title (or the URL if Folio returned no title), then `saved` or the error. End with the count saved, for example `Saved 4 of 5 to Folio; 1 failed (HTTP 422)`.
