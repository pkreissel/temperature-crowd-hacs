# 0004 — Locally-held bearer token + coarsen location at the edge

- Status: Accepted (mirrors server ADR-0004)
- Date: 2026-06-29

## Context
Server ADR-0004 proposes a blind-issued bearer token so the donor's email and data are
cryptographically unlinkable. That guarantee only holds if the **payload itself** is
non-identifying — and a precise home location re-identifies regardless of token anonymity.
The integration sits at the edge, where the donor's precise location is known (HA `zone.home`,
configured lat/long), so the edge is where coarsening must happen.

## Decision
- During the config flow the integration runs the **RFC 9474 blind-issuance** exchange
  (server ADR-0004): blind a client-chosen message, get it signed after email verification,
  unblind, and store the resulting **credential `(msg, sig)` locally** (HA config entry). It is
  presented on every upload; the server verifies it (RSA-PSS) and groups data under
  `hash(msg)`. Because erasure is bearer-driven, surface "keep this credential to manage/delete
  your data" prominently in the config flow.
- **Coarsen location before anything leaves the house** (per server ADR-0003), entirely
  client-side from the precise coords (HA `zone.home`); never transmit precise coordinates:
  1. project lat/long → ETRS89-LAEA, floor to the candidate INSPIRE cells;
  2. pick the **emission level** by membership tests against a **bundled safe-cell bitmask**
     (population ≥ T). At **T = 25,000** the finest reachable level is **10 km**: emit the 10 km
     cell if its bit is set, else the 100 km parent (1 km is not reached at this T);
  3. attach **climate region A/B/C** from the same lookup.
  - The bitmask (a <1 KB 10 km safe-mask at T = 25,000; built server-side from Zensus 2022,
    parameterized by T/basis/vintage) ships **inside the integration release** → fully offline
    decision, no network query, no location leak. The "bulk public data, offline decision" pattern.
  - The client decides the at-rest floor on **residents** (static census), never on **donor**
    counts — counting donors would leak the cell and deadlock coordination (server ADR-0003).
- Room tagging (room type, floor, orientation, build year) is collected in the config flow as
  coarse metadata only.

## Open questions
- Where the PLZ→region + grid mapping lives (bundled table vs. one-time server lookup that
  itself must not log precise coords or client IP).
- Credential storage security within the HA config entry; issuer-key rotation handling.
- Whether the blinding/unblinding runs in a small bundled Python lib vs. a vetted dependency.
- `device_id` is generated client-side (random, rotatable) — confirmed, grouping key only.

## Consequences
- Edge coarsening becomes a **hard requirement** of the integration, not an option.
- Donor holds the only handle to their data (token) — strong privacy, weaker recovery UX.
