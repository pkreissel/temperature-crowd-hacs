# 0001 — Custom integration via HACS, not an add-on

- Status: Accepted
- Date: 2026-06-29

## Context
"Plugin" in Home Assistant can mean a custom integration, a Supervisor add-on, or a
blueprint/automation. The decisive requirement is the **historical backfill**: reading
long-term statistics is only possible from **inside the HA process** (recorder APIs).

- **Add-on** runs as a Docker container, exists only on HA OS/Supervised (excludes
  Container/Core users), and can only reach HA over the API — it cannot read LTS directly.
- **Blueprint / `rest_command`** can stream live data but cannot perform the LTS backfill.
- **Custom integration** runs in-process, can call the recorder statistics APIs, provides a
  UI config flow, and works on **every** install type.

## Decision
Ship a **custom integration** distributed via **HACS**.

## Consequences
- Works on all HA install types; full access to LTS for backfill.
- Standard skeleton: `manifest.json`, `config_flow.py`, `__init__.py`, `coordinator.py`,
  `const.py`, plus `hacs.json`.
- Keep the generic JSON-POST / Ecowitt paths (server side) as fallback so HA is the *best*
  path, not the *only* path.
