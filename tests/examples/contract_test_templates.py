"""Exemplary Contract Test Templates.

This file contains reference implementations of contract-based tests that follow
the testing standards defined in TESTING_STANDARDS.md. Use these as templates
when writing new tests.

KEY PRINCIPLES:
- Test WHAT the code does (inputs → outputs), not HOW it does it
- Mock external boundaries (HTTP, file system), not internal methods
- Assert on observable outcomes, not internal state or call sequences
- Tests should only fail when behavior changes, not when code is refactored

CONTRACT TESTING PATTERNS:

1. Public API Testing with Boundary Mocking
2. Auto-Connect Behavior Testing
3. Error Handling Testing
4. Bulk Operation Testing
5. Multi-Domain Operation Testing
6. Data Validation Testing
7. Integration Testing with External Dependencies
"""

import pytest
from unittest.mock import AsyncMock, patch
import json

# ==============================================================================
# TEMPLATE 1: Public API Testing with Boundary Mocking
# ==============================================================================
# CONTRACT: Test public methods through their inputs and outputs
# BOUNDARY: Mock external HTTP calls, not internal implementation


class TemplateEntityRetrieval:
    """Template for testing entity retrieval through public APIs.

    GOOD EXAMPLE: Tests public API (get_entity_state) with HTTP boundary mocked.
    BAD ALTERNATIVE: Would mock internal _make_request or _process_entity methods.
    """

    @pytest.mark.asyncio
    async def test_get_entity_state_returns_correct_data(self, ha_client):
        """Test that get_entity_state returns the correct entity data.

        CONTRACT: Given a valid entity_id, the method should return that
        entity's state data from Home Assistant. Tests WHAT data is returned,
        not HOW it was retrieved.
        """
        expected_data = {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"brightness": 255},
        }

        # Mock the HTTP boundary (acceptable boundary mocking)
        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = expected_data

            # Call the public API
            result = await ha_client.get_entity_state("light.living_room")

            # Assert on CONTRACT: correct data returned
            assert result == expected_data
            assert result["state"] == "on"
            assert result["attributes"]["brightness"] == 255

            # Verify boundary call (confirms correct endpoint used)
            mock_request.assert_called_once_with("GET", "/api/states/light.living_room")


# ==============================================================================
# TEMPLATE 2: Auto-Connect Behavior Testing
# ==============================================================================
# CONTRACT: Operations should succeed regardless of initial connection state
# FOCUS: Test the OUTCOME (operation succeeds), not the mechanism (connect called)


class TemplateAutoConnect:
    """Template for testing auto-connect behavior through outcomes.

    GOOD EXAMPLE: Tests that operations succeed when starting disconnected.
    BAD ALTERNATIVE: Would assert connect.assert_called_once().
    """

    @pytest.mark.asyncio
    async def test_operation_succeeds_when_initially_disconnected(
        self, server_with_mocks
    ):
        """Test that operations succeed regardless of initial connection state.

        CONTRACT: Operations should auto-connect if needed and return valid data.
        Tests WHAT happens (operation succeeds), not HOW (connection established).
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.session = None  # Start disconnected
        mock_ha_client.get_entity_state.return_value = {
            "entity_id": "light.test",
            "state": "on",
        }

        # Get the registered tool function
        tool_calls = server.mcp.tool.call_args_list
        get_state_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_entity_state"
        )

        # Call the function
        result = await get_state_func("light.test")

        # Assert on CONTRACT: operation succeeded and returned valid data
        parsed = json.loads(result)
        assert parsed["entity_id"] == "light.test"
        assert parsed["state"] == "on"

        # Verify the outcome (API was called)
        mock_ha_client.get_entity_state.assert_called_once_with("light.test")


# ==============================================================================
# TEMPLATE 3: Error Handling Testing
# ==============================================================================
# CONTRACT: Test that errors are properly propagated and handled
# FOCUS: Test WHAT errors are raised, not internal error handling mechanisms


class TemplateErrorHandling:
    """Template for testing error handling through public APIs.

    GOOD EXAMPLE: Tests error propagation through observable exceptions.
    BAD ALTERNATIVE: Would mock internal error handling methods.
    """

    @pytest.mark.asyncio
    async def test_api_error_propagates_to_caller(self, ha_client):
        """Test that API errors are properly propagated.

        CONTRACT: When the API returns an error, the appropriate exception
        should be raised to the caller. Tests WHAT error is raised, not HOW
        error handling works internally.
        """
        from src.mcp_hass.ha_client import HomeAssistantAPIError

        # Mock boundary to return error
        with patch.object(
            ha_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = HomeAssistantAPIError("Entity not found", 404)

            # Assert on CONTRACT: correct exception raised
            with pytest.raises(HomeAssistantAPIError) as exc_info:
                await ha_client.get_entity_state("light.nonexistent")

            assert exc_info.value.status_code == 404
            assert "Entity not found" in str(exc_info.value)


# ==============================================================================
# TEMPLATE 4: Bulk Operation Testing
# ==============================================================================
# CONTRACT: Test bulk operations return aggregated results correctly
# FOCUS: Test WHAT aggregated results look like, not HOW items were processed


class TemplateBulkOperation:
    """Template for testing bulk operations through outcomes.

    GOOD EXAMPLE: Tests aggregated results match expected structure.
    BAD ALTERNATIVE: Would mock internal _process_item or loop implementation.
    """

    @pytest.mark.asyncio
    async def test_bulk_operation_returns_aggregated_results(
        self, server_with_mocks, sample_service_response
    ):
        """Test that bulk operations return correct aggregated results.

        CONTRACT: Bulk operation should process all items and return summary
        with total, succeeded, and failed counts. Tests WHAT the aggregated
        result contains, not HOW individual items were processed.
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.call_service.return_value = sample_service_response

        tool_calls = server.mcp.tool.call_args_list
        turn_on_bulk_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "turn_on_bulk"
        )

        entity_ids = ["light.living_room", "light.bedroom", "light.kitchen"]
        result = await turn_on_bulk_func(entity_ids)

        # Assert on CONTRACT: aggregated results are correct
        parsed = json.loads(result)
        assert parsed["total"] == 3
        assert parsed["succeeded"] == 3
        assert parsed["failed"] == 0
        assert len(parsed["results"]) == 3

        # Verify each result has expected structure
        for item in parsed["results"]:
            assert "entity_id" in item
            assert "success" in item

        # Verify service was called for each entity (outcome verification)
        assert mock_ha_client.call_service.call_count == 3


# ==============================================================================
# TEMPLATE 5: Multi-Domain Operation Testing
# ==============================================================================
# CONTRACT: Operations handle multiple domains correctly
# FOCUS: Test WHAT services are called for each domain, not HOW domain extraction works


class TemplateMultiDomain:
    """Template for testing multi-domain operations through outcomes.

    GOOD EXAMPLE: Tests that correct domain services are called for each entity.
    BAD ALTERNATIVE: Would mock _extract_domain or test domain parsing logic.
    """

    @pytest.mark.asyncio
    async def test_multi_domain_operation_calls_correct_services(
        self, server_with_mocks, sample_service_response
    ):
        """Test that operations correctly handle entities from different domains.

        CONTRACT: When processing entities from multiple domains (light, switch, fan),
        the correct domain service should be called for each. Tests WHAT services
        are called, not HOW domains are extracted.
        """
        server, mock_ha_client = server_with_mocks
        mock_ha_client.call_service.return_value = sample_service_response

        tool_calls = server.mcp.tool.call_args_list
        turn_on_bulk_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__") and call[0][0].__name__ == "turn_on_bulk"
        )

        # Mix of different domains
        entity_ids = ["light.living_room", "switch.kitchen", "fan.bedroom"]
        result = await turn_on_bulk_func(entity_ids)

        # Assert on CONTRACT: operation succeeded
        assert result is not None
        parsed = json.loads(result)
        assert parsed["total"] == 3

        # Verify correct domain services were called (outcome verification)
        call_args_list = mock_ha_client.call_service.call_args_list
        expected_domains = ["light", "switch", "fan"]

        for i, call_args in enumerate(call_args_list):
            args, kwargs = call_args
            assert args[0] == expected_domains[i]  # Correct domain
            assert args[1] == "turn_on"  # Correct service
            assert args[2]["entity_id"] == entity_ids[i]  # Correct entity


# ==============================================================================
# TEMPLATE 6: Data Validation Testing
# ==============================================================================
# CONTRACT: Invalid input should be rejected with appropriate errors
# FOCUS: Test WHAT inputs are accepted/rejected, not HOW validation works


class TemplateDataValidation:
    """Template for testing input validation through outcomes.

    GOOD EXAMPLE: Tests validation results for various inputs.
    BAD ALTERNATIVE: Would mock _validate_input or test validation regex.
    """

    @pytest.mark.asyncio
    async def test_invalid_entity_id_rejected(self, server_with_mocks):
        """Test that invalid entity IDs are rejected.

        CONTRACT: Entity IDs must follow 'domain.entity_name' format.
        Invalid formats should raise appropriate errors. Tests WHAT inputs
        are rejected, not HOW validation is implemented.
        """
        server, mock_ha_client = server_with_mocks

        tool_calls = server.mcp.tool.call_args_list
        get_state_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "get_entity_state"
        )

        # Assert on CONTRACT: invalid inputs raise errors
        invalid_entity_ids = ["invalid_no_dot", ".", ".only_entity", "only_domain.", ""]

        for invalid_id in invalid_entity_ids:
            with pytest.raises(Exception):  # Or specific validation error
                await get_state_func(invalid_id)

    def test_service_data_validation(self, ha_client):
        """Test service data validation through public API.

        CONTRACT: Service data must be a dictionary. Invalid types should
        return False from validation. Tests WHAT inputs are valid, not HOW
        validation logic works.
        """
        # Valid data
        assert (
            ha_client.validate_service_data("light", "turn_on", {"brightness": 255})
            is True
        )

        # Invalid data types
        invalid_data = ["not a dict", 123, ["list", "of", "items"], None]

        for data in invalid_data:
            assert ha_client.validate_service_data("light", "turn_on", data) is False


# ==============================================================================
# TEMPLATE 7: Integration Testing with External Dependencies
# ==============================================================================
# CONTRACT: Test realistic workflows with mocked external boundaries
# FOCUS: Test WHAT the complete workflow produces, not internal coordination


class TemplateIntegration:
    """Template for integration testing with boundary mocking.

    GOOD EXAMPLE: Tests complete workflows through public APIs.
    BAD ALTERNATIVE: Would test internal coordination methods separately.
    """

    @pytest.mark.asyncio
    async def test_complete_workflow_from_query_to_result(self, server_with_mocks):
        """Test a complete workflow from tool invocation to formatted result.

        CONTRACT: A tool should accept input, interact with Home Assistant,
        and return properly formatted output. Tests the COMPLETE behavior,
        not individual steps.
        """
        server, mock_ha_client = server_with_mocks

        # Setup mocks for external boundaries
        mock_ha_client.get_all_states.return_value = [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "light.bedroom", "state": "off"},
            {"entity_id": "switch.kitchen", "state": "on"},
        ]

        # Get the tool function
        tool_calls = server.mcp.tool.call_args_list
        filter_func = next(
            call[0][0]
            for call in tool_calls
            if hasattr(call[0][0], "__name__")
            and call[0][0].__name__ == "filter_entities_by_state"
        )

        # Execute complete workflow
        result = await filter_func("on")

        # Assert on CONTRACT: complete workflow produces correct output
        parsed = json.loads(result)
        assert len(parsed) == 2  # Two entities with state "on"
        assert any(e["entity_id"] == "light.living_room" for e in parsed)
        assert any(e["entity_id"] == "switch.kitchen" for e in parsed)
        assert not any(e["entity_id"] == "light.bedroom" for e in parsed)

        # Verify external boundary was called correctly
        mock_ha_client.get_all_states.assert_called_once()


# ==============================================================================
# ANTI-PATTERNS TO AVOID
# ==============================================================================


class AntiPatternsToAvoid:
    """Examples of what NOT to do - these violate contract testing principles."""

    # ❌ BAD: Testing internal methods directly
    def test_internal_method_directly_BAD(self, server):
        """DON'T test private methods directly."""
        result = server._extract_domain("light.test")  # ❌ Testing internal method
        assert result == "light"

    # ❌ BAD: Mocking internal implementation
    @pytest.mark.asyncio
    async def test_mocking_internal_implementation_BAD(self, server):
        """DON'T mock internal methods to test public APIs."""
        with patch.object(
            server, "_process_entity"
        ) as mock_process:  # ❌ Mock internal
            mock_process.return_value = "processed"
            await server.get_entity("light.test")
            mock_process.assert_called_once()  # ❌ Assert internal call

    # ❌ BAD: Testing implementation details
    @pytest.mark.asyncio
    async def test_implementation_details_BAD(self, ha_client):
        """DON'T test HOW code works internally."""
        await ha_client.get_entity_state("light.test")
        # ❌ Testing that connect was called (implementation detail)
        ha_client.connect.assert_called_once()

    # ❌ BAD: Asserting internal state
    @pytest.mark.asyncio
    async def test_internal_state_BAD(self, server):
        """DON'T assert on internal state variables."""
        await server.initialize()
        # ❌ Testing internal state instead of observable behavior
        assert server._initialized is True
        assert len(server._tool_registry) > 0

    # ✅ GOOD: Testing observable outcomes
    @pytest.mark.asyncio
    async def test_observable_outcomes_GOOD(self, server):
        """DO test observable behavior and outcomes."""
        await server.initialize()
        # ✅ Testing that tools are registered (observable through public API)
        tool_names = server.get_registered_tools()
        assert "get_entity_state" in tool_names
        assert len(tool_names) >= 15


# ==============================================================================
# USAGE GUIDELINES
# ==============================================================================
"""
When writing new tests, use these templates as reference:

1. ENTITY RETRIEVAL: Use Template 1 for testing GET operations
2. AUTO-CONNECT: Use Template 2 for testing connection behavior
3. ERROR HANDLING: Use Template 3 for testing error cases
4. BULK OPERATIONS: Use Template 4 for testing aggregated operations
5. MULTI-DOMAIN: Use Template 5 for testing domain-specific behavior
6. VALIDATION: Use Template 6 for testing input validation
7. INTEGRATION: Use Template 7 for end-to-end workflows

KEY QUESTIONS TO ASK:
- Am I testing WHAT the code does, or HOW it does it?
- Would this test break if I refactored the implementation?
- Am I mocking external boundaries, or internal methods?
- Do my assertions verify observable outcomes, or internal state?

If you answer "HOW", "yes", "internal", or "internal state" - reconsider your approach!
"""
