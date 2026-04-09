# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-08

### Added

- MCP server with stdio and streamable HTTP transport modes
- Home Assistant REST API client with connection validation
- WebSocket API client with automatic reconnection
- Entity tools: list, get state, search, and history queries
- Service tools: list domains, list services, and call services
- Device tools: list devices with area/entity resolution
- Spatial tools: list areas and floors with device mapping
- Camera tools: capture snapshots with automatic image optimization
- Token-aware response truncation for large payloads
- CLI with `run`, `init`, and `validate` commands
- Docker support with multi-stage build and non-root execution
- Cloudflare Tunnel deployment configuration for remote access
- CI pipeline with pytest, black, flake8, bandit, and pip-audit
