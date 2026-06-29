# Architecture Decision Records — HACS integration (client)

Each file records one decision: context → decision → consequences. Append-only —
supersede with a new ADR rather than editing an accepted one.

| # | Title | Status |
|---|-------|--------|
| [0001](0001-custom-integration-not-addon.md) | Custom integration via HACS, not an add-on | Accepted |
| [0002](0002-backfill-via-long-term-statistics.md) | Backfill via long-term statistics + live coordinator | Accepted |
| [0003](0003-separate-repo-versioned-contract.md) | Separate repo, consumes the versioned contract | Accepted |
| [0004](0004-client-token-edge-coarsening.md) | Locally-held blind-signed credential + coarsen location at the edge | Accepted |

Cross-repo: see `../../../server/docs/adr` for the server ADRs this client depends on
(notably server 0004 identity, 0006 contract).
