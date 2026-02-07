#!/usr/bin/env python3
"""
Integration tests for session-aware data loading.

Tests the data_name workflow where tools reference data stored in the R workspace
instead of passing inline data.
"""

from shutil import which

import pytest

pytestmark = pytest.mark.skipif(
    which("R") is None, reason="R binary is required for session data tests"
)

from rmcp.core.context import Context, LifespanState  # noqa: E402
from rmcp.tools.session_data import (  # noqa: E402
    DataValidationError,
    validate_data_params,
)


async def create_test_context(session_enabled: bool = True) -> Context:
    """Create a test context for tool execution."""
    lifespan = LifespanState()
    lifespan.r_session_enabled = session_enabled
    context = Context.create("test", "test", lifespan)
    return context


class TestDataParamValidation:
    """Test the Python-side data/data_name validation."""

    def test_validate_with_data_present(self):
        """Test validation passes when data is provided."""
        params = {"data": {"x": [1, 2, 3], "y": [4, 5, 6]}}
        # Should not raise
        validate_data_params(params)

    def test_validate_with_data_name_present(self):
        """Test validation passes when data_name is provided."""
        params = {"data_name": "my_dataset"}
        # Should not raise
        validate_data_params(params)

    def test_validate_with_both_present(self):
        """Test validation passes when both data and data_name are provided."""
        params = {"data": {"x": [1, 2, 3]}, "data_name": "my_dataset"}
        # Should not raise - both present is valid
        validate_data_params(params)

    def test_validate_with_neither_present(self):
        """Test validation fails when neither data nor data_name is provided."""
        params = {"x": "value", "y": "value"}
        with pytest.raises(DataValidationError) as exc_info:
            validate_data_params(params)
        assert "No data provided" in str(exc_info.value)
        assert "data_name" in str(exc_info.value)

    def test_validate_with_empty_data(self):
        """Test validation fails when data is None."""
        params = {"data": None}
        with pytest.raises(DataValidationError):
            validate_data_params(params)

    def test_validate_with_empty_data_name(self):
        """Test validation fails when data_name is empty string."""
        params = {"data_name": ""}
        with pytest.raises(DataValidationError):
            validate_data_params(params)

    def test_validate_with_require_data_false(self):
        """Test validation passes when require_data is False."""
        params = {}  # No data at all
        # Should not raise because require_data=False
        validate_data_params(params, require_data=False)

    def test_validate_with_custom_data_param(self):
        """Test validation with custom data parameter name."""
        params = {"input_data": {"x": [1, 2, 3]}}
        # Should pass with custom param name
        validate_data_params(params, data_param="input_data")

        # Should fail when looking for default "data"
        with pytest.raises(DataValidationError):
            validate_data_params(params, data_param="data")


class TestSessionDataSchemas:
    """Test session data schema modifications."""

    def test_add_data_name_param_adds_property(self):
        """Test that add_data_name_param adds data_name to schema."""
        from rmcp.tools.session_data import add_data_name_param

        original_schema = {
            "type": "object",
            "properties": {
                "data": {"type": "object"},
                "x": {"type": "string"},
            },
            "required": ["data", "x"],
        }

        modified = add_data_name_param(original_schema)

        # Should have data_name added
        assert "data_name" in modified["properties"]
        assert modified["properties"]["data_name"]["type"] == "string"

        # Should have data removed from required
        assert "data" not in modified["required"]
        assert "x" in modified["required"]

    def test_add_data_name_param_preserves_original(self):
        """Test that original schema is not modified."""
        from rmcp.tools.session_data import add_data_name_param

        original_schema = {
            "type": "object",
            "properties": {"data": {"type": "object"}},
            "required": ["data"],
        }

        add_data_name_param(original_schema)

        # Original should be unchanged
        assert "data_name" not in original_schema["properties"]
        assert "data" in original_schema["required"]

    def test_add_data_name_param_timeseries(self):
        """Test that timeseries variant works correctly."""
        from rmcp.tools.session_data import add_data_name_param_timeseries

        original_schema = {
            "type": "object",
            "properties": {
                "data": {"type": "object"},
            },
            "required": ["data"],
        }

        modified = add_data_name_param_timeseries(original_schema)

        # Should have data_name with timeseries-specific description
        assert "data_name" in modified["properties"]
        desc = modified["properties"]["data_name"]["description"]
        assert "ts" in desc.lower() or "time series" in desc.lower()

    def test_add_output_data_name_param(self):
        """Test that output_data_name is added correctly."""
        from rmcp.tools.session_data import add_output_data_name_param

        original_schema = {
            "type": "object",
            "properties": {"data": {"type": "object"}},
        }

        modified = add_output_data_name_param(original_schema)

        assert "output_data_name" in modified["properties"]
        assert modified["properties"]["output_data_name"]["type"] == "string"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
