# 0002 — Backfill via long-term statistics + live coordinator

- Status: Accepted
- Date: 2026-06-29

## Context
HA keeps two history tiers:
- **Raw `states`** — purged after `purge_keep_days` (default 10 days); reachable via REST
  `/api/history/period/`. Useless for backfill on a default install.
- **Long-term statistics (LTS)** — for any sensor with `state_class: measurement` (virtually
  all temperature sensors), HA stores **hourly mean/min/max** and **never purges** it. 24
  rows/day, kept for years. Reachable only via the **WebSocket** `statistics_during_period`
  (or the `recorder.get_statistics` action) — **not** REST.

This LTS tier is the platform's unique advantage: a donor with two summers of HA history can
contribute two years of hourly indoor temperature in one import, instead of starting from zero.

## Decision
Two modes in the integration:
1. **One-time backfill** — query `statistics_during_period`, `period: "hour"`, for the
   selected entities over their full available range; map mean→`temp_c`, min→`temp_c_min`,
   max→`temp_c_max`; POST in chunks (~1–2k rows) to `/v1/ingest`.
2. **Ongoing live** — a `DataUpdateCoordinator` appends new hourly stats thereafter.

Resilience: local buffer + idempotent retries (server upserts on `(device_id, ts)`).

## Consequences
- Backfill is bursty (~17k points / 2 yr / sensor); rely on batch + idempotent upsert.
- Hourly **mean** smooths peaks (slight ÜTGS under-count); shipping **max** lets the server
  compute the peak variant (server ADR-0002).
- Must detect sensors **without** `state_class: measurement` (no LTS) and warn the donor.
- LTS DB reads must run in the recorder executor, not the event loop.
