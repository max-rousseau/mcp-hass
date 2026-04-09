# MCP-HASS Tool Selection Guide

Choose the right tool for efficient Home Assistant interaction:

## Entity Discovery Tools

### find_entities
**Use when:** You know what you're looking for and want filtered results.
- Searching by entity name pattern: `find_entities(name="temperature")`
- Filtering by domain: `find_entities(domain="light")`
- Finding entities by state: `find_entities(domain="light", state="on")`
- Filtering by device_class: `find_entities(device_class="motion")`

**Avoid when:** Exploring an unknown area or needing device information.

### list_areas → get_area_devices → get_device_entities
**Use when:** Exploring or organizing by physical location.
- "What devices are in the kitchen?"
- "Show me everything in the bedroom"
- "I want to control all devices in the living room"
- When you need device metadata (manufacturer, model, firmware)

**Flow:**
1. `list_areas()` - Get all area names and IDs
2. `get_area_devices(area_name="Kitchen")` - Get devices in that area
3. `get_device_entities(device_id="...")` - Get entities per device

## Quick Reference Table

| Task | Best Tool(s) |
|------|--------------|
| Find all lights | `find_entities(domain="light")` |
| Find lights in bedroom | `list_areas` → `get_area_devices` → `get_device_entities` |
| Find entities by name | `find_entities(name="living room")` |
| Explore an area | `list_areas` → `get_area_devices` → `get_device_entities` |
| Check entity state | `find_entities(name="exact_entity_id")` |
| Find motion sensors | `find_entities(device_class="motion")` |
| List available areas | `list_areas()` |
| Get device info | `get_area_devices(area_name="X")` |

## Service Calling

### call_service
**Use for:** Single entity operations
```
call_service(domain="light", service="turn_on", entity_id="light.bedroom")
```

### call_service_bulk
**Use for:** Multiple entities with same action
```
call_service_bulk(domain="light", service="turn_off", entity_ids=["light.a", "light.b"])
```

## Efficiency Tips

1. **Start broad, then narrow:** Use `list_areas()` first when exploring
2. **Use hierarchical tools for location queries:** They provide device context
3. **Use find_entities for targeted searches:** When you know domain/name/class
4. **Batch operations:** Use `call_service_bulk` for multiple entities
5. **Check services first:** Use `get_services()` then `get_service_detail()` to understand available actions
