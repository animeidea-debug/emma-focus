# Codex morning-brief integration

## Decision

Emma Focus exposes a separate, versioned `focus-brief:read` projection for
Codex morning briefs. The repository-owned `emma-focus-morning-brief` plugin
uses only that projection through two MCP tools: `check_connection` and
`get_focus_brief`.

## Boundaries

- The projection is read-only and derives wallet facts from
  `token_transactions`; it never recalculates or changes ledger history.
- Tokens are random, stored only as SHA-256 hashes, limited to one scope,
  expire within one year, and can be revoked by a parent using the normal PIN.
- The MCP server reads the scoped token from macOS Keychain. It receives no
  parent PIN, browser session, full database, or production write credential.
- Missing evaluation data remains `missing`, not zero. `pending_review`
  remains provisional.
- TMOS-linked wallet settlements are grouped once and never expanded into
  duplicate underlying task rewards.

## Consequences

The plugin must be configured only after a reviewed backend release. A brief
may describe authoritative stored facts but cannot repair, evaluate, reward,
redeem, exchange, or submit data. Cross-product composition joins TMOS and
Emma Focus only by local date; each product remains authoritative for its own
facts.
