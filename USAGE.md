# MCP-HASS Usage Guide

## Command Line Interface

The MCP-HASS server can be launched and managed using the command-line interface.

### Basic Usage

```bash
# Show help
mcp-hass --help

# Start the server
mcp-hass serve

# Start with custom configuration
mcp-hass serve --ha-url http://X.X.X.X:8123 --ha-token your_token_here

# List all available tools
mcp-hass tools

# List tools in JSON format
mcp-hass tools --output json

# Validate Home Assistant connection
mcp-hass validate

# Show current configuration
mcp-hass config
```

### Configuration

The server uses environment variables or a `.env` file for configuration:

```bash
# Using environment file
mcp-hass serve --env-file /path/to/.env

# Using command line overrides
mcp-hass serve \
  --ha-url http://X.X.X.X:8123 \
  --ha-token your_long_lived_access_token \
  --timeout 30 \
  --validate

# Skip connection validation (faster startup)
mcp-hass serve --no-validate
```

### Required Environment Variables

Create a `.env` file with:

```bash
HA_BASE_URL=http://your-hass-ip:8123
HA_TOKEN=your_long_lived_access_token
```

### Available Commands

- `serve` - Start the MCP server
- `init` - Initialize configuration file at `~/.config/mcp-hass/config`
- `validate` - Test Home Assistant connection
- `tools` - List available MCP tools
- `config` - Show current configuration

### MCP Tools Summary

The server provides 12 tools across 7 categories:

1. **Entity Tools** (2) - Entity discovery and historical state data
2. **Service Tools** (3) - Service control, discovery (summary), and detail lookup
3. **Spatial Tools** (2) - Area/zone-based queries
4. **Device Tools** (2) - Device discovery and device-entity relationship mapping
5. **Bulk Tools** (1) - Multi-entity operations
6. **Camera Tools** (1) - Camera snapshot capture with intelligent downsampling
7. **Config Tools** (1) - YAML configuration validation and reload

Use `mcp-hass tools` to see the complete list with descriptions.