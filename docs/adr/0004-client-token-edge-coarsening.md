# 0004 — Locally-held Reusable OPRF token + coarsen location at the edge

- Status: Accepted (mirrors server ADR-0004)
- Date: 2026-06-29

## Context
Server ADR-0004 specifies using an Oblivious Pseudorandom Function (OPRF) so the donor's email and data are cryptographically unlinkable, while preserving the ability to link a donor's historical data together.

## Decision
- During the config flow, the integration runs the **OPRF blinding** exchange: the client generates a random nonce `X` (pseudonym), blinds it, and sends it to the server. After email verification, the server returns the blinded `OPRF(k, X)`. The client unblinds it and stores `(X, OPRF(k, X))` locally as the credential.
- **Upload Auth**: On every upload, the client sends `(X, OPRF(k, X))`. The server re-evaluates `X` using its secret key `k` and verifies it matches.
- **pyoprf / libsodium** will be used to implement the client-side blinding and unblinding mathematically securely.
- **Coarsen location before anything leaves the house**: derive only grid cell / PLZ + climate region (A/B/C) client-side; never transmit precise coordinates.
