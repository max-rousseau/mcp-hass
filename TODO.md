# TODO

## Post-Release

- [ ] `ha_client/client.py:get_history()` — Pass `entity_id` and timestamps via `params=` dict instead of string interpolation into URL path/query
- [ ] `tools/camera.py` — Snapshot files accumulate in `/config/www/snaps/` with no cleanup (two UUID-named JPEGs per call). Add cleanup of stale snapshot after fresh one is captured, or implement a TTL/rotation strategy
- [ ] Create `SECURITY.md` with private vulnerability disclosure policy (email-based reporting)
- [ ] Create `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1)
- [ ] Create GitHub issue/PR templates (`.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`)
- [ ] `ha_client/client.py:call_service()` — Validate `domain` and `service` params with `^[a-z][a-z0-9_]*$` regex before URL interpolation (path traversal hardening)
- [ ] `tools/entity.py:get_entity_history()` — Clamp `hours` parameter to a reasonable maximum (e.g., 8760 = 1 year)
- [ ] `tools/bulk.py:call_service_bulk()` — Add max entity count cap on `entity_ids` list
