#!/usr/bin/env python3
"""
Simple test script to verify Home Assistant API connection and entity access.
Tests the entity that's reportedly failing: sensor.hue_motion_yellow_illuminance
"""

import asyncio
import sys
from pathlib import Path

from src.mcp_hass.config import ConfigurationManager
from src.mcp_hass.ha_client import HomeAssistantClient

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_entity_state():
    """Test getting entity state directly from Home Assistant."""

    print("=" * 60)
    print("Home Assistant API Test")
    print("=" * 60)

    # Load configuration
    print("\n1. Loading configuration...")
    try:
        config = ConfigurationManager()
        print(f"   ✓ HA URL: {config.get_ha_base_url()}")
        print(f"   ✓ Token: {'*' * 20}...{config.get_ha_token()[-4:]}")
        print(f"   ✓ Timeout: {config.get_ha_timeout()}s")
    except Exception as e:
        print(f"   ✗ Configuration error: {e}")
        return

    # Create client
    print("\n2. Creating Home Assistant client...")
    client = HomeAssistantClient(
        base_url=config.get_ha_base_url(),
        token=config.get_ha_token(),
        timeout=config.get_ha_timeout(),
    )

    # Connect
    print("\n3. Connecting to Home Assistant...")
    try:
        await client.connect()
        print("   ✓ Connected successfully")
    except Exception as e:
        print(f"   ✗ Connection failed: {e}")
        return

    # Validate connection
    print("\n4. Validating connection...")
    try:
        is_valid = await client.validate_connection()
        if is_valid:
            print("   ✓ Connection validated")
            config_data = await client.get_config()
            print(f"   ✓ HA Version: {config_data.get('version', 'unknown')}")
            print(f"   ✓ Location: {config_data.get('location_name', 'unknown')}")
        else:
            print("   ✗ Connection validation failed")
            return
    except Exception as e:
        print(f"   ✗ Validation error: {e}")
        return

    # Test the specific entity (without _lux suffix to test our error handling)
    test_entity = "sensor.hue_motion_yellow_illuminance"  # Missing _lux suffix!
    print(f"\n5. Testing entity: {test_entity}")
    print("-" * 40)

    try:
        # First, check if entity exists in all states
        print("   a. Getting all states to verify entity exists...")
        all_states = await client.get_all_states()
        entity_ids = [s.get("entity_id") for s in all_states]

        if test_entity in entity_ids:
            print(
                f"   ✓ Entity found in state list (total entities: {len(entity_ids)})"
            )
        else:
            print("   ✗ Entity NOT found in state list!")
            print(f"   Total entities: {len(entity_ids)}")

            # Show similar entities
            similar = [e for e in entity_ids if "illuminance" in e.lower()]
            if similar:
                print("   Similar entities found:")
                for e in similar[:5]:
                    print(f"      - {e}")

            # Show all hue motion sensors
            hue_motion = [e for e in entity_ids if "hue_motion" in e.lower()]
            if hue_motion:
                print("   Hue motion sensors found:")
                for e in hue_motion[:10]:
                    print(f"      - {e}")

        # Now try to get the specific entity
        print(f"\n   b. Getting state for {test_entity}...")
        state_data = await client.get_entity_state(test_entity)

        print("   ✓ Entity state retrieved successfully!")
        print(f"   State: {state_data.get('state', 'unknown')}")
        print("   Attributes:")
        for key, value in state_data.get("attributes", {}).items():
            print(f"      - {key}: {value}")

    except Exception as e:
        print(f"   ✗ Error getting entity state: {e}")
        print(f"   Error type: {type(e).__name__}")

        # Try alternate entity IDs
        print("\n   c. Trying alternate entity ID formats...")
        alternates = [
            test_entity.lower(),
            test_entity.upper(),
            test_entity.replace("_", "-"),
        ]

        for alt in alternates:
            if alt != test_entity:
                print(f"      Trying: {alt}")
                try:
                    state_data = await client.get_entity_state(alt)
                    print(f"      ✓ Success with {alt}!")
                    break
                except Exception:
                    print("      ✗ Failed")

    finally:
        # Disconnect
        print("\n6. Disconnecting...")
        await client.disconnect()
        print("   ✓ Disconnected")

    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_entity_state())
