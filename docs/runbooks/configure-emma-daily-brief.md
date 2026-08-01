# Configure the Emma Daily Brief

## Prerequisites

- Deploy a reviewed Emma Focus release containing the `focus-brief:read` API.
- Install or upgrade the marketplace plugin `emma-daily-brief@family` in Codex.
- Run token exchange on the home LAN; do not put a PIN or token in Git, shell
  history, URLs, or configuration files.

## Configure

Use the marketplace repository's current `configure.mjs` with the LAN base URLs
for both services. The exact command and flags are maintained with the plugin,
not duplicated in this product repository.

The interactive setup prompts for the parent PIN without echoing it, exchanges
it once for scoped read tokens, stores the tokens in macOS Keychain, and writes
only non-secret endpoint configuration to the local config file.

## Verify

Ask Codex to run `check_connection`, then `get_tmos_brief` and
`get_focus_brief`. A failed check means stop and resolve connectivity or
authorization; do not fall back to a browser session or expose the parent PIN.

## Parent management

Use the Admin-authenticated token-management endpoints to list token metadata or
revoke a lost/unused token. Token secrets are returned only at issuance, are
never stored in plaintext, and expire after at most the configured maximum.
