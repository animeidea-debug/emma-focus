# Configure the Emma Focus Codex morning brief

## Prerequisites

- Deploy a reviewed Emma Focus release containing the focus-brief backend.
- Install the repository-owned `emma-focus-morning-brief` plugin in Codex.
- You must run the token exchange **on your home LAN** (connected to the same
  network as the NAS). ZConnect (极空间) remote access intercepts API requests
  from CLI tools without a browser session cookie.

## Step 1: Find your LAN URL

On the home network, the NAS API is available at:

```
http://192.168.6.108:8888/api/poc
```

If you changed the NAS IP or port, adjust accordingly. You can verify by
opening `http://192.168.6.108:8888/admin.html` in a browser.

## Step 2: Exchange PIN for token (LAN only)

In an interactive terminal on the parent Mac, run:

```sh
node plugins/emma-focus-morning-brief/scripts/configure.mjs \
  --base-url http://192.168.6.108:8888/api/poc \
  --expires-days 90
```

The script will:
1. Probe the endpoint to confirm it is not being intercepted by ZConnect.
2. Prompt for the parent PIN (hidden input).
3. Exchange the PIN for a scoped read-only token.
4. Store the token in macOS Keychain.
5. Write the base URL to `~/.config/emma-focus-morning-brief/config.json`.

## Step 3: Verify

Ask Codex to run `check_connection`, then `get_focus_brief`. A failed check
means stop and resolve configuration or authorization.

## Remote access (optional)

After obtaining the token on LAN, you can edit the config file to use the
ZConnect HTTPS URL for remote access:

```sh
# Edit: ~/.config/emma-focus-morning-brief/config.json
# Change baseUrl from http://192.168.6.108:8888/api/poc to:
#   https://remote-access-8888.zconnect.cn/api/poc
```

Note: ZConnect may or may not forward the `Authorization: Bearer ...` header.
If `check_connection` fails remotely, switch back to the LAN URL or use
Tailscale for direct access.

## Parent management

Use the Admin-authenticated focus-brief token endpoints to list token metadata
and revoke a lost or unused token. Token secrets are returned only at issuance,
are never stored in plaintext, and expire after at most 365 days.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Endpoint returned a redirect` | ZConnect intercepting the request | Run on LAN with `http://192.168.6.108:8888/api/poc` |
| `Invalid parent PIN` | Wrong PIN | Re-enter the current Admin PIN |
| `Too many failed PIN attempts` | 5 failures in 5 minutes | Wait 5 minutes and retry |
| `authorization is missing` | Token not in Keychain | Re-run configure.mjs |
| `token is invalid or expired` | Token revoked/expired | Re-run configure.mjs |
