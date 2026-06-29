# 0003 — Separate repo, consumes the versioned contract

- Status: Accepted
- Date: 2026-06-29

## Context
HACS installs an integration by cloning a GitHub repo that has `custom_components/<domain>/`
**at the repo root**, using **tagged releases** as versions. It has no clean way to install
from a subdirectory of a monorepo. The integration is also a different toolchain (Python +
HA test harness), a different release cadence (driven by HA/HACS, not server deploys), and is
installed on machines we do not control — so it must tolerate version skew with the server.

## Decision
- The integration lives in its **own repo** (this folder, to be split out), root-level
  `custom_components/temperaturcrowd/` + `hacs.json` + tagged releases.
- The server + web + contract live in a separate monorepo.
- The integration **consumes the versioned ingest contract** (`server/packages/contract`),
  pins a contract version, and runs contract tests in CI.

## Consequences
- HACS works as intended; integration releases are independent of server deploys.
- Version skew is explicit and safe because the contract is additive-only (server ADR-0006).
- Integration bug reports land in the integration repo, not the backend tracker.
