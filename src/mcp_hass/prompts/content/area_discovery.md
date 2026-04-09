# Area-Based Entity Discovery Workflow

When you need to find and control entities in a specific area/room, use this
hierarchical approach instead of searching with find_entities:

## Step 1: List all areas
```
list_areas()
```
This returns all defined areas with their area_id and name.

## Step 2: Get devices in the target area
```
get_area_devices(area_name="Living Room")
```
This returns all devices assigned to that area, including their device_id.

## Step 3: Get entities for specific devices
```
get_device_entities(device_id="abc123...")
```
This returns all entities belonging to that device.

## Example Flow

User asks: "Turn on all lights in the bedroom"

1. First, call `list_areas()` to find the bedroom area
2. Then call `get_area_devices(area_name="Bedroom")` to get all devices there
3. For each device, call `get_device_entities(device_id=...)` to find light entities
4. Finally, use `call_service_bulk()` to turn on all discovered lights

## When to Use This Pattern

- When you know the area/room name but not the specific entity IDs
- When you want to discover ALL entities in a location (not just one domain)
- When you need device-level information (manufacturer, model, etc.)
- When the area has many devices and you want organized results

## Comparison with find_entities

| Approach | Best For |
|----------|----------|
| Hierarchical (this workflow) | Area exploration, device discovery, organized results |
| find_entities(area="X") | Quick single-domain queries when you know what you want |
