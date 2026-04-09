# MCP-HASS API Reference

This document provides comprehensive API reference for all tools, resources, and prompts available in MCP-HASS.

## Tool Reference

MCP-HASS provides **12 fully functional tools** across **7 categories** for comprehensive Home Assistant data access and control.

### Entity Tools (2 tools)

Tools for entity discovery and historical state data using the REST API.

#### `find_entities`

Find Home Assistant entities with flexible filtering and OData-like field selection. This is the primary entity discovery tool.

**Parameters:**
- `name` (string, optional): Substring to match entity_id or friendly_name (use `"*"` for all, default: `"*"`)
- `domain` (string, optional): Domain filter (e.g., `"light"`, `"sensor"`, `"switch"`)
- `area` (string, optional): Area name filter (e.g., `"bedroom"`, `"kitchen"`)
- `device_class` (string, optional): Device class filter (e.g., `"temperature"`, `"motion"`)
- `state` (string, optional): State value filter (e.g., `"on"`, `"off"`, `"unavailable"`)
- `attributes` (object, optional): Attribute filters as dict - all key-value pairs must match
- `select` (array of strings, optional): Additional scalar fields to include. Valid: `"state"`, `"last_changed"`, `"last_updated"`
- `expand` (array of strings, optional): Nested objects to fully include. Valid: `"attributes"` (full), `"context"`

**Returns:** JSON array of matching entities. Default fields: `entity_id`, `attributes.friendly_name`. Additional fields included only if requested via `select`/`expand` parameters.

**Examples:**

Find all bedroom lights:
```json
{
  "name": "find_entities",
  "arguments": {
    "domain": "light",
    "area": "bedroom"
  }
}
```

Find all lights that are currently ON (include state):
```json
{
  "name": "find_entities",
  "arguments": {
    "domain": "light",
    "state": "on",
    "select": ["state"]
  }
}
```

Find temperature sensors with timestamps and full attributes:
```json
{
  "name": "find_entities",
  "arguments": {
    "device_class": "temperature",
    "select": ["state", "last_changed"],
    "expand": ["attributes"]
  }
}
```

---

#### `get_entity_history`

Get historical state data for an entity.

**Parameters:**
- `entity_id` (string, required): Entity ID to get history for
- `hours` (float, optional): Number of hours of history to retrieve (default: 24.0)

**Returns:**
JSON object with entity metadata in the header and a compact array of state changes. Structure:
- `entity_id`: The entity identifier
- `attributes`: Entity attributes (friendly_name, unit_of_measurement, device_class)
- `history`: Array of historical state objects with `state` and `last_changed` fields

**Example Response:**
```json
{
  "entity_id": "sensor.temperature",
  "attributes": {
    "friendly_name": "Temperature",
    "unit_of_measurement": "°F",
    "device_class": "temperature"
  },
  "history": [
    {"state": "72.5", "last_changed": "2025-12-11T01:15:49+00:00"},
    {"state": "73.0", "last_changed": "2025-12-11T01:30:00+00:00"}
  ]
}
```

**Token Limit:**
Subject to `TOOL_TOKEN_LIMIT` environment variable. If response exceeds the limit, an error is returned with token count information and suggestion to reduce the `hours` parameter.

---

### Service Tools (3 tools)

Tools for device control and service discovery using the REST API.

#### `call_service`

Call a Home Assistant service to control devices or trigger actions.

**Parameters:**
- `domain` (string, required): Service domain (e.g., "light", "switch", "climate")
- `service` (string, required): Service name (e.g., "turn_on", "turn_off", "set_temperature")
- `entity_id` (string, optional): Target entity ID
- `data` (object, optional): Additional service data

**Returns:**
JSON array of affected entities with their new states after service execution.

**Example Requests:**

Turn on light with brightness:
```json
{
  "name": "call_service",
  "arguments": {
    "domain": "light",
    "service": "turn_on", 
    "entity_id": "light.kitchen_island",
    "data": {
      "brightness": 200,
      "color_temp": 320
    }
  }
}
```

Set climate temperature:
```json
{
  "name": "call_service",
  "arguments": {
    "domain": "climate",
    "service": "set_temperature",
    "entity_id": "climate.living_room",
    "data": {
      "temperature": 72,
      "hvac_mode": "heat"
    }
  }
}
```

---

#### `get_services`

Get a compact summary of all available Home Assistant services.

**Parameters:** None

**Returns:**
JSON array of domain summaries listing available services in compact format. Each object contains:
- `domain`: Service domain name (e.g., "light", "switch", "climate")
- `services`: Array of service names available in that domain

**Example Response:**
```json
[
  {"domain": "light", "services": ["turn_on", "turn_off", "toggle"]},
  {"domain": "switch", "services": ["turn_on", "turn_off", "toggle"]},
  {"domain": "climate", "services": ["set_temperature", "set_hvac_mode", "turn_on", "turn_off"]}
]
```

**Token Limit:**
This tool is subject to the `TOOL_TOKEN_LIMIT` environment variable to prevent token bloat. If the response would exceed the configured limit, an error is returned with token count information instead.

**Use Case:**
Use this tool to discover available services across all domains. After finding a service you want to use, call `get_service_detail()` to get the full schema with field definitions, types, requirements, and examples.

---

#### `get_service_detail`

Get detailed schema information for a specific Home Assistant service.

**Parameters:**
- `domain` (string, required): Service domain (e.g., "light", "switch", "climate")
- `service` (string, required): Service name (e.g., "turn_on", "turn_off", "set_temperature")

**Returns:**
JSON object containing the complete service definition:
- `domain`: The service domain
- `service`: The service name
- `fields`: Detailed field definitions including types, requirements, examples, and selectors

**Example Request:**
```json
{
  "name": "get_service_detail",
  "arguments": {
    "domain": "light",
    "service": "turn_on"
  }
}
```

**Example Response:**
```json
{
  "domain": "light",
  "service": "turn_on",
  "fields": {
    "brightness": {
      "description": "Number indicating brightness",
      "example": 120,
      "selector": {"number": {"min": 0, "max": 255}},
      "values": {"min": 0, "max": 255}
    },
    "color_temp": {
      "description": "Color temperature in mireds",
      "selector": {"number": {"min": 153, "max": 500}},
      "values": {"min": 153, "max": 500}
    },
    "rgb_color": {
      "description": "Color in RGB format",
      "example": [255, 100, 100]
    }
  }
}
```

**Raises:**
- `ValueError`: If domain or service not found (includes helpful suggestions of available options)

**Use Case:**
After using `get_services()` to discover available services, use this tool to get complete field definitions before calling `call_service()`. This provides all the information needed to construct valid service calls with proper parameters.

---

### Spatial Tools (2 tools)

Tools for area-based queries and spatial intelligence using WebSocket API.

#### `list_areas`

Get all areas/zones defined in Home Assistant.

**Parameters:** None

**Returns:**
JSON array of area objects with metadata.

**Example Response:**
```json
[
  {
    "area_id": "living_room",
    "name": "Living Room",
    "aliases": ["lounge", "main room"]
  },
  {
    "area_id": "bedroom",
    "name": "Bedroom",
    "aliases": []
  }
]
```

**Use Cases:**
- Area discovery for spatial queries
- Building area-aware automations
- Understanding home layout

---

#### `get_area_devices`

Get all devices in a specific area/zone.

**Parameters:**
- `area_name` (string, required): Name of the area to get devices for

**Returns:**
JSON array of device objects with manufacturer, model, and configuration details.

**Example Request:**
```json
{
  "name": "get_area_devices",
  "arguments": {
    "area_name": "kitchen"
  }
}
```

**Example Response:**
```json
[
  {
    "id": "device123",
    "name": "Kitchen Light Switch",
    "manufacturer": "Lutron",
    "model": "PD-6WCL-WH",
    "area_id": "kitchen",
    "via_device_id": null,
    "disabled_by": null,
    "configuration_entries": ["config_entry_1"]
  }
]
```

---

### Device Tools (2 tools)

Tools for device discovery and device-entity relationship mapping using WebSocket API.

#### `find_devices`

Find Home Assistant devices with filtering and OData-like field selection.

Primary device discovery tool. Devices represent physical hardware (e.g., a Hue bulb, thermostat, or smart plug) and have a 1:N relationship with entities. Uses OData-like `select` and `expand` parameters to control response size for token efficiency.

**Parameters:**
- `name` (string, optional): Substring to match device name (use `"*"` for all, default: `"*"`)
- `manufacturer` (string, optional): Manufacturer filter (e.g., `"Philips"`, `"Ecobee"`)
- `model` (string, optional): Model filter (e.g., `"Hue White Ambiance"`)
- `area` (string, optional): Area name filter (e.g., `"bedroom"`, `"kitchen"`)
- `select` (array of strings, optional): Additional scalar fields to include. Valid: `"manufacturer"`, `"model"`, `"model_id"`, `"sw_version"`, `"hw_version"`, `"serial_number"`, `"via_device_id"`
- `expand` (array of strings, optional): Nested objects to fully include. Valid: `"entities"` (full entity data), `"identifiers"`, `"connections"`

**Returns:**
JSON array of matching devices. **Default fields:** `id`, `name`, `area_id`, `entities` (minimal: entity_id + friendly_name)

Additional fields included only if requested via `select` or `expand` parameters.

**Examples:**

Find all devices (minimal response):
```json
{
  "name": "find_devices",
  "arguments": {}
}
```

Find devices by manufacturer:
```json
{
  "name": "find_devices",
  "arguments": {
    "manufacturer": "Philips"
  }
}
```

Find devices in an area with model info:
```json
{
  "name": "find_devices",
  "arguments": {
    "area": "bedroom",
    "select": ["manufacturer", "model"]
  }
}
```

Find devices with full entity data:
```json
{
  "name": "find_devices",
  "arguments": {
    "manufacturer": "Ecobee",
    "expand": ["entities"]
  }
}
```

---

#### `get_device_entities`

Get all entities associated with a specific device.

**Parameters:**
- `device_id` (string, required): The device ID to get entities for

**Returns:**
JSON array of entity registry entries associated with the device.

**Example Request:**
```json
{
  "name": "get_device_entities",
  "arguments": {
    "device_id": "device123"
  }
}
```

**Use Cases:**
- Understanding what entities belong to a device
- Device-based automation and control
- Troubleshooting device issues

---

### Bulk Tools (1 tool)

Efficient multi-entity operations using REST API.

#### `call_service_bulk`

Call a service on multiple entities at once.

**Parameters:**
- `domain` (string, required): Service domain (e.g., 'light', 'switch')
- `service` (string, required): Service name (e.g., 'turn_on', 'turn_off')
- `entity_ids` (array, required): Array of entity IDs to apply service to
- `data` (object, optional): Additional service data applied to all entities

**Returns:**
JSON object with bulk operation results, success/failure count, and per-entity results.

**Example Request:**
```json
{
  "name": "call_service_bulk",
  "arguments": {
    "domain": "light",
    "service": "turn_off",
    "entity_ids": [
      "light.kitchen_ceiling",
      "light.kitchen_island",
      "light.kitchen_under_cabinet"
    ]
  }
}
```

**Example Response:**
```json
{
  "total": 3,
  "succeeded": 3,
  "failed": 0,
  "results": [
    {
      "entity_id": "light.kitchen_ceiling",
      "success": true,
      "result": {...}
    }
  ]
}
```

---

### Camera Tools (1 tool)

Tools for camera image capture and processing.

#### `get_camera_snapshot`

Capture and return a snapshot from any Home Assistant camera entity with intelligent downsampling for AI analysis.

**Parameters:**
- `entity_id` (string, required): Camera entity ID (e.g., "camera.front_door")

**Returns:**
JSON object containing:
- `success`: Boolean indicating success
- `image_base64`: Base64-encoded JPEG data
- `snapshot_id`: UUID v4 identifier
- `original_size`: Original image dimensions
- `final_size`: Final image dimensions after downsampling
- `downsampled`: Boolean indicating if downsampling was applied

**Example Response:**
```json
{
  "success": true,
  "image_base64": "<base64-encoded JPEG data>",
  "snapshot_id": "550e8400-e29b-41d4-a716-446655440000",
  "original_size": "3840x2160",
  "final_size": "1024x576",
  "downsampled": true
}
```

**Implementation Details:**
- Automatically downsamples images >1024px using high-quality LANCZOS resampling
- Preserves aspect ratio
- Takes two snapshots to avoid stale cached frames (RTSP stream workaround)
- Returns optimized JPEG with 85% quality for efficient AI processing

---

### Configuration Management Tools (1 tool)

Tools for Home Assistant configuration validation and reloading.

#### `reload_yaml_config`

Validate and reload all Home Assistant YAML configuration.

First validates all YAML configuration files for syntax and semantic correctness. If validation passes, reloads all YAML-based configuration without requiring a full Home Assistant restart.

**Parameters:** None

**Returns:**
`"YAML configuration validated and reloaded successfully."`

**Raises:** `ValueError` if:
- Validation fails (reload is NOT performed) - includes detailed error messages
- Home Assistant validation API is unavailable

---

## Resource Reference

MCP-HASS provides **2 FastMCP resources** for structured access to Home Assistant data.

### `mcp-hass://config`

Get Home Assistant configuration, version, and system details.

**Returns:**
JSON object containing:
- `version`: Home Assistant version
- `location_name`: Configured location name
- `time_zone`: System timezone
- `unit_system`: Unit system (metric/imperial)
- `config_dir`: Configuration directory path
- `whitelist_external_dirs`: External directory whitelist
- `components`: List of loaded components

**Example Response:**
```json
{
  "version": "2024.1.0",
  "location_name": "Home",
  "time_zone": "America/New_York", 
  "unit_system": {
    "length": "km",
    "mass": "kg",
    "temperature": "°C",
    "volume": "L"
  },
  "components": [
    "automation",
    "light",
    "sensor",
    "switch"
  ]
}
```

---

### `mcp-hass://config-guide`

Get detailed Home Assistant configuration structure guide.

**Returns:**
Comprehensive markdown documentation explaining:
- Configuration directory structure
- Include directive patterns
- Best practices for editing
- File naming conventions
- Entity organization patterns

---

## Prompt Reference

### `discover_area_entities`

Hierarchical discovery workflow for finding entities in a specific area.

Demonstrates the efficient area -> device -> entity discovery pattern, which is more targeted than using `find_entities` with broad filters.

**Parameters:** None

**Returns:** Guided workflow instructions for area-based entity discovery.

---

### `tool_selection_guide`

Guide for selecting the most efficient tool for entity discovery tasks.

**Parameters:** None

**Returns:** Decision guide for choosing between `find_entities`, `find_devices`, `list_areas`, and other discovery tools.

---

## Error Reference

### Common Error Types

#### Configuration Errors
```json
{
  "error": "configuration_error",
  "message": "Required environment variable 'HA_BASE_URL' is not set",
  "variable_name": "HA_BASE_URL",
  "hint": "Please check .env.example for configuration guidance"
}
```

#### Connection Errors
```json
{
  "error": "connection_error", 
  "message": "Failed to connect to Home Assistant at http://X.X.X.X:8123",
  "details": "Connection refused",
  "remedy": "Check if Home Assistant is running and accessible"
}
```

#### Entity Not Found Errors
```json
{
  "error": "entity_not_found",
  "requested_entity": "light.nonexistent",
  "message": "Entity 'light.nonexistent' not found in Home Assistant",
  "suggestions": [
    "light.bedroom_ceiling", 
    "light.bedroom_lamp"
  ],
  "hint": "Did you mean one of these? The most likely match is 'light.bedroom_ceiling'"
}
```

#### Authentication Errors
```json
{
  "error": "authentication_error",
  "message": "Invalid Home Assistant token",
  "remedy": "Generate a new long-lived access token in Home Assistant"
}
```

#### API Errors
```json
{
  "error": "api_error",
  "message": "Service 'invalid_service' not found in domain 'light'",
  "status_code": 400,
  "available_services": ["turn_on", "turn_off", "toggle"]
}
```

### Error Recovery

Most errors trigger automatic recovery mechanisms:
1. **Connection Errors**: Automatic retry with fresh connection
2. **Timeout Errors**: Exponential backoff retry
3. **WebSocket Errors**: Automatic reconnection
4. **Session Errors**: New session creation

Only authentication and configuration errors require manual intervention.

---

## Schema Reference

All tools include JSON Schema definitions that guide LLM usage:

```json
{
  "name": "find_entities",
  "description": "Find entities with flexible filtering options",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {
        "type": "string",
        "description": "Substring to match entity_id or friendly_name - use '*' for all",
        "default": "*"
      },
      "domain": {
        "type": "string", 
        "description": "Optional domain filter (e.g., light, sensor)"
      },
      "area": {
        "type": "string",
        "description": "Optional area filter (e.g., bedroom, kitchen)" 
      },
      "device_class": {
        "type": "string",
        "description": "Optional device class filter (e.g., temperature, motion)"
      }
    }
  }
}
```

These schemas enable LLMs to:
- Understand tool capabilities and parameters
- Validate arguments before calling
- Choose optimal tools for specific queries
- Construct proper API calls

This comprehensive API reference provides all the information needed to effectively use MCP-HASS for Home Assistant integration through the Model Context Protocol.