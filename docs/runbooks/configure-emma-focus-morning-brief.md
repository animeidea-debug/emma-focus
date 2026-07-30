# Configure the Emma Focus Codex morning brief

## Prerequisites

- Deploy a reviewed Emma Focus release containing the focus-brief backend.
- Install the repository-owned `emma-focus-morning-brief` plugin in Codex.
- Use the external HTTPS base URL ending in `/api/poc`; do not put a PIN or
  token in Git, shell history, URLs, or configuration files.

## Parent setup

In an interactive terminal on the parent Mac, run:

```sh
node plugins/emma-focus-morning-brief/scripts/configure.mjs \
  --base-url https://your-emma-focus-host/api/poc \
  --expires-days 90
```

The script requests the parent PIN without echoing it, exchanges it once for a
scoped read token, saves that token in macOS Keychain, and writes only the
non-secret base URL to `~/.config/emma-focus-morning-brief/config.json` with
owner-only permissions.

## Parent management

Use the Admin-authenticated focus-brief token endpoints to list token metadata
and revoke a lost or unused token. Token secrets are returned only at issuance,
are never stored in plaintext, and expire after at most 365 days.

## Verify

Ask Codex to run `check_connection`, then `get_focus_brief`. A failed check
means stop and resolve configuration or authorization; do not fall back to a
browser session or a parent PIN.
