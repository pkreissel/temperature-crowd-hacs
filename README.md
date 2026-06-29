# TemperaturCrowd — Home Assistant integration

HACS-distributed custom integration. Will become its own git repo (HACS expects
`custom_components/<domain>/` at the repo root with tagged releases).

## What it does
1. **Config flow** — donor enters platform API key + accepts consent/DSGVO terms.
2. **Entity selection + room tagging** — pick real indoor sensors, tag room/floor/orientation/build year.
3. **Backfill** — read long-term statistics via `statistics_during_period` (`period: "hour"`,
   mean/min/max), map to the canonical schema, POST in batches. The unique advantage:
   years of existing hourly history, not zero-from-install.
4. **Live** — `DataUpdateCoordinator` appends new hourly stats thereafter.
5. **Resilience** — local buffer + idempotent retries.

Consumes the versioned contract from `../server/packages/contract`.

## Layout
- `custom_components/temperaturcrowd/` — `manifest.json`, `config_flow.py`, `__init__.py`,
  `coordinator.py`, `const.py`.
- `hacs.json` — HACS metadata (repo root once split out).
