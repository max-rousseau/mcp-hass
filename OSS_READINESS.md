# Open Source Release Readiness Audit

**Date:** 2026-04-09
**Repository:** mcp-hass
**Auditor:** Full re-audit (secrets, source, docs, config, CI, Docker)

---

## Scope

Comprehensive audit of every git-tracked file for information leakage, security issues, and public-release readiness. TODO.md items (already deferred by user) and previously-fixed items are NOT re-raised here.

## Open Findings

| # | Severity | Issue | Description | Proposed Solution | Status |
|---|----------|-------|-------------|-------------------|--------|
| 1 | MEDIUM | Inconsistent release maturity signaling | `pyproject.toml:15` declared `Development Status :: 3 - Alpha`, but `pyproject.toml:7` sets `version = "1.0.0"` and `CHANGELOG.md` records a 1.0.0 release on 2026-04-08. A 1.0.0 package labeled Alpha confuses downstream users and PyPI consumers about stability guarantees. | Updated classifier to `"Development Status :: 4 - Beta"` to match the declared 1.0.0 version. | FIXED |

---

## Verified Clean (no action)

| Area | Result |
|------|--------|
| Hardcoded private IPs / hostnames / MACs | PASS — all source and test fixtures use `X.X.X.X`, `homeassistant.local`, or clearly-synthetic values |
| Personal info leakage (emails, absolute paths, home dir) | PASS — only `Maxime Rousseau` in `pyproject.toml` authors field, which is standard and intentional |
| Secrets, tokens, API keys in source or git history | PASS — all placeholders, no real credentials in last 30 commits |
| SSH keys / certs / private keys | PASS — none present |
| `.gitignore` coverage (`.env`, tfstate, tfvars, logs, caches) | PASS |
| SPDX license headers on all 25 Python source files | PASS |
| TLS verification enabled by default, warning when disabled | PASS (`client.py`, `websocket_client.py`) |
| Auth header redaction in debug middleware | PASS (`http/middleware.py:59-60`) |
| No `eval` / `exec` / `pickle` / unsafe YAML / `subprocess` | PASS |
| Input validation at MCP tool boundaries | PASS (entity ID regex, URL scheme, timeouts) |
| CI workflow runs `bandit`, `pip-audit`, `flake8`, `black`, `pytest` | PASS |
| Dockerfile: multi-stage, non-root user, healthcheck | PASS |
| `.env.example` has safe placeholders only | PASS |
| LICENSE.md (BSD-3-Clause) consistent with pyproject + classifier | PASS |
| README, CONTRIBUTING, CHANGELOG, USAGE, docs/API_REFERENCE.md | PASS |
| Dependencies pinned with `~=`, all from PyPI | PASS |
| Git history: no sensitive data, all commits use GitHub noreply | PASS |

---

## Deferred Items (already in TODO.md, not re-raised)

- `SECURITY.md` — private vulnerability disclosure policy
- `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1
- GitHub issue/PR templates
- `ha_client/client.py:get_history()` URL parameter encoding
- `tools/camera.py` snapshot cleanup
- `ha_client/client.py:call_service()` domain/service regex validation
- `tools/entity.py:get_entity_history()` hours clamping
- `tools/bulk.py:call_service_bulk()` entity count cap

---

## Revalidation Log (2026-04-09)

- Row 1 (MEDIUM, Alpha classifier vs 1.0.0): VERIFIED — `pyproject.toml:15` still reads `"Development Status :: 3 - Alpha"` while `pyproject.toml:7` is `version = "1.0.0"` and `CHANGELOG.md:8` records `[1.0.0] - 2026-04-08`. Retained.
- Row 2 (LOW, missing `keywords`): REMOVED — severity below MEDIUM threshold.
- Row 3 (LOW, `git` in Docker runtime): REMOVED — severity below MEDIUM threshold.
- Row 4 (INFO, stray working-tree files): REMOVED — severity below MEDIUM threshold.
