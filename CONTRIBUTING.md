# Contributing to MCP-HASS

Thank you for contributing to MCP-HASS! This document provides guidelines for code and test contributions.

## Development Setup

1. Clone the repository
2. Create virtual environment: `python -m venv .venv`
3. Install dependencies: `./.venv/bin/pip install -e ".[dev]"`
4. Install pre-commit hooks: `./hooks/install.sh`

## Architecture Overview

MCP-HASS uses a modular, dependency-injection architecture. See the Architecture section in `README.md` for diagrams and overview.

### Key Design Principles

1. **Thin Orchestrator**: `server.py` only handles initialization and coordination
2. **Dependency Injection**: `ToolContext` provides all dependencies to tool modules
3. **No Global State**: All state passed explicitly via context objects
4. **Focused Modules**: Each tool module handles a single domain
5. **Explicit Errors**: No silent fallbacks - fail with helpful error messages
6. **Token Awareness**: All tools check token limits before returning large responses

### Adding New Tools

Quick summary:

1. Create new module in `src/mcp_hass/tools/` (e.g., `automation.py`)
2. Define `register_automation_tools(ctx: ToolContext)` function
3. Use `@ctx.mcp.tool()` decorator for tool functions
4. Access dependencies via `ctx`: `ctx.ha_client`, `ctx.logger`, `ctx.config`
5. Register in `tools/__init__.py` and add to `__all__`

Example:
```python
def register_automation_tools(ctx: "ToolContext") -> None:
    @ctx.mcp.tool()
    async def my_tool(param: str) -> str:
        """Tool description for LLM."""
        data = await ctx.ha_client.get_all_states()
        ctx.logger.debug(f"Processing {len(data)} items")
        # Check token limits, format response
        return json.dumps(data)
```

## Code Standards

- Follow PEP 8
- Use type hints for all functions
- Keep functions focused and concise
- Use ToolContext for all dependencies (no global state)
- Implement token limit checking for all tools returning large data
- See coding standards in user documentation for details

## Testing Standards

**CRITICAL**: All tests must follow contract-based testing principles.

### PR Review Checklist: Testing

Before submitting a PR, ensure your tests pass this checklist:

#### ✅ Contract-Based Testing
- [ ] Tests verify WHAT the code does (inputs → outputs), not HOW it works internally
- [ ] Tests assert on observable outcomes, not internal method calls
- [ ] Tests only mock external boundaries (HTTP, file system), not internal methods
- [ ] Tests would NOT break if implementation is refactored while maintaining behavior

#### ❌ Implementation Anti-Patterns to Avoid
- [ ] ~~No tests calling private methods directly (methods starting with `_`)~~
- [ ] ~~No mocking of private/internal methods~~
- [ ] ~~No assertions on internal state variables~~
- [ ] ~~No `assert_called_once()` on internal method calls~~
- [ ] ~~No testing of HOW code works instead of WHAT it produces~~

#### 📋 Test Structure
- [ ] Test names describe behavior, not implementation
- [ ] Each test has a clear CONTRACT statement in docstring
- [ ] Tests use boundary mocking (HTTP, DB) not internal mocking
- [ ] Error tests verify exception types and messages, not error handling implementation

#### 🔍 Auto-Connect Pattern (if applicable)
- [ ] Tests verify operations succeed, NOT that `connect()` was called
- [ ] Mock data is returned from operations, not from internal methods
- [ ] Assertions check operation results, not connection state

#### 🎯 Domain Extraction Pattern (if applicable)
- [ ] Tests verify correct domain service is called
- [ ] NO mocking or testing of `_extract_domain()` method
- [ ] Assertions check service call arguments, not domain parsing logic

### Examples

See `tests/examples/contract_test_templates.py` for 7 exemplary test patterns.


## Pre-Commit Hooks

Pre-commit hooks automatically check for common test anti-patterns:

- Mocking private methods (`patch.object` with `_method`)
- Asserting calls on private methods
- Over-mocking with `patch.multiple`

To bypass (not recommended): `git commit --no-verify`

## Running Tests

```bash
# Run all tests
./.venv/bin/pytest tests/

# Run specific test file
./.venv/bin/pytest tests/test_entity_tools.py

# Run with coverage
./.venv/bin/pytest tests/ --cov=src/mcp_hass --cov-report=html
```

## Smoke Testing

Smoke tests validate a running mcp-hass instance end-to-end using the MCP Inspector CLI. Requires `npx` (Node.js), `jq`, and `curl`.

```bash
# Full pipeline: build, start, smoke test
./launch.sh

# Or run smoke tests against an already-running instance
./scripts/smoke-test.sh                           # defaults to localhost:3000
./scripts/smoke-test.sh http://localhost:9000/mcp  # custom URL
```

The smoke test checks:
1. HTTP readiness (MCP Streamable HTTP endpoint responding)
2. Tool discovery (all 10 tools registered)
3. Resource discovery (both resources registered)
4. Live read-only call (`list_areas` against your HA instance)

## Pull Request Process

1. Create feature branch from `main`
2. Write code following standards above
3. Add/update tests (contract-based!)
4. Ensure all tests pass
5. Pre-commit hooks must pass
6. Submit PR with clear description

## Questions?

- Review `tests/examples/contract_test_templates.py` for reference implementations
