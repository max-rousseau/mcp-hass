# Home Assistant Configuration Structure Guide

## Overview
This Home Assistant installation uses an organized, split-configuration approach with extensive use of `!include` directives. The main `configuration.yaml` acts as an orchestrator that pulls in specialized configuration files from organized subdirectories.

## Directory Structure

```
hass_config/                           # Root configuration directory
├── configuration.yaml                 # Main orchestrator file
├── scripts.yaml                      # Global scripts (direct include)
├── automations.yaml                  # Legacy automations (direct include)
├── secrets.yaml                      # Sensitive data (referenced via !secret)
├── ui-lovelace.yaml                  # Main Lovelace config
│
├── configs/                          # Primary configuration directory
│   ├── automation/                   # Individual automation files
│   │   ├── abode.yaml               # Security system automations
│   │   ├── caseta_picos.yaml        # Lutron Pico remote automations
│   │   ├── hue_dimmer_kitchen.yaml  # Hue dimmer automations
│   │   ├── hue_tap_red.yaml         # Hue tap device automations
│   │   ├── office.yaml              # Office-specific automations
│   │   ├── utilities.yaml           # Utility automations
│   │   └── ...                      # Other automation files
│   │
│   ├── sensor/                      # Sensor configuration files
│   │   ├── templates.yaml           # Template sensors
│   │   ├── energy_sensors.yaml     # Energy monitoring sensors
│   │   ├── purple_air.yaml         # Air quality sensors
│   │   └── statistics.yaml         # Statistical sensors
│   │
│   ├── switch/                      # Switch configuration files
│   │   ├── mqtt_switches.yaml      # MQTT-based switches
│   │   └── templates.yaml          # Template switches
│   │
│   ├── lovelace/                    # Dashboard configuration files
│   │   ├── 1-home.yaml             # Main dashboard
│   │   ├── 2-baby.yaml             # Baby room dashboard
│   │   ├── 3-masterbed.yaml        # Master bedroom dashboard
│   │   └── ...                     # Other dashboard files
│   │
│   ├── lights.yaml                 # Light configuration (single file)
│   ├── groups.yaml                 # Groups configuration
│   ├── scenes.yaml                 # Scene definitions
│   ├── homekit.yaml                # HomeKit integration config
│   ├── mqtt.yaml                   # MQTT broker configuration
│   └── ...                         # Other single config files
│
├── esphome/                         # ESPHome device configurations
│   ├── esphome-web-24e57b.yaml    # Individual ESP device configs
│   └── ...                        # Other ESP device files
│
├── insteon-mqtt/                   # Insteon-MQTT integration files
│   ├── config.yaml                # Insteon-MQTT main config
│   ├── devices.yaml               # Device definitions
│   └── data/                      # Device-specific data files
│
└── zigbee2mqtt/                    # Zigbee2MQTT configuration
    └── configuration.yaml          # Z2M config file
```

## Include Directive Patterns

The main `configuration.yaml` uses several include patterns:

### Single File Includes
```yaml
# Direct file inclusion
script: !include scripts.yaml
light: !include configs/lights.yaml
homekit: !include configs/homekit.yaml
```

### Directory Merge Lists
```yaml
# Merge all YAML files in directory into a list
sensor: !include_dir_merge_list configs/sensor/
switch: !include_dir_merge_list configs/switch/
automation: !include_dir_merge_list configs/automation/
```

### Directory Merge Named
```yaml
# Merge files as named dictionary entries
frontend:
  themes: !include_dir_merge_named themes/
```

## Configuration Categories

### Core System Files
- `configuration.yaml` - Main orchestrator (contains !include directives)
- `secrets.yaml` - Sensitive data (tokens, passwords, etc.)

### Automation Files (`configs/automation/`)
- Device-specific: `hue_tap_*.yaml`, `hue_dimmer_*.yaml`, `caseta_picos.yaml`
- Room-specific: `office.yaml`, `evelyns_room.yaml`
- System-specific: `abode.yaml`, `utilities.yaml`, `washer_dryer.yaml`

### Sensor Files (`configs/sensor/`)
- `templates.yaml` - Template sensors using Jinja2
- `energy_sensors.yaml` - Energy monitoring
- `purple_air.yaml` - Air quality monitoring
- `statistics.yaml` - Statistical calculations

### Switch Files (`configs/switch/`)
- `mqtt_switches.yaml` - MQTT-controlled switches
- `templates.yaml` - Template switches

### Interface Files (`configs/lovelace/`)
- Numbered dashboards: `1-home.yaml`, `2-baby.yaml`, etc.
- Feature-specific: `sensors.yaml`, `cooling.yaml`, `upstairs.yaml`

## Best Practices for Editing

### DO:
- Edit files in the `configs/` subdirectories for most changes
- Add new automation files to `configs/automation/` (auto-included)
- Add new sensor files to `configs/sensor/` (auto-included)
- Preserve existing indentation and formatting
- Use consistent naming: room/device-specific files

### DON'T:
- Modify !include directives in `configuration.yaml` without understanding impact
- Edit files outside `hass_config/` directory
- Change the overall directory structure
- Mix different configuration types in the same file

## Entity Organization

Entities are organized by function and location:
- **Room-based**: office, master bedroom, baby room, kitchen
- **Device-based**: hue devices, caseta switches, ESPHome sensors
- **System-based**: energy monitoring, MQTT, security (Abode)

## File Naming Conventions

- **Devices**: `{device_type}_{identifier}.yaml` (e.g., `hue_tap_red.yaml`)
- **Rooms**: `{room_name}.yaml` (e.g., `office.yaml`, `evelyns_room.yaml`)
- **Functions**: `{function}.yaml` (e.g., `utilities.yaml`, `energy_sensors.yaml`)
- **Dashboards**: `{number}-{name}.yaml` (e.g., `1-home.yaml`, `2-baby.yaml`)

This structure allows for:
- Easy maintenance and organization
- Granular control over different aspects
- Clear separation of concerns
- Git-friendly change tracking
- Collaborative editing without conflicts
