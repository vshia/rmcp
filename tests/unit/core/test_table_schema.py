#!/usr/bin/env python3
"""
Unit tests for table_schema validation.

Tests that table_schema correctly validates both column-oriented and row-oriented
data formats while rejecting invalid inputs.
"""

import pytest
from jsonschema import validate, ValidationError

from rmcp.core.schemas import table_schema


class TestTableSchemaValidation:
    """Test table_schema validation for different data formats."""

    def test_column_oriented_valid(self):
        """Test that valid column-oriented data passes validation."""
        schema = table_schema()
        data = {"col1": [1, 2, 3], "col2": [4, 5, 6]}
        # Should not raise
        validate(instance=data, schema=schema)

    def test_row_oriented_valid(self):
        """Test that valid row-oriented data passes validation."""
        schema = table_schema()
        data = [
            {"col1": 1, "col2": 4},
            {"col1": 2, "col2": 5},
            {"col1": 3, "col2": 6},
        ]
        # Should not raise
        validate(instance=data, schema=schema)

    def test_single_column_valid(self):
        """Test that single column data passes validation."""
        schema = table_schema()
        data = {"x": [1, 2, 3, 4, 5]}
        validate(instance=data, schema=schema)

    def test_single_row_valid(self):
        """Test that single row data passes validation."""
        schema = table_schema()
        data = [{"x": 1, "y": 2}]
        validate(instance=data, schema=schema)

    def test_empty_object_valid(self):
        """Test that empty object passes validation (validated at runtime in R)."""
        schema = table_schema()
        data = {}
        # Empty object passes JSON Schema but R will validate at runtime
        validate(instance=data, schema=schema)

    def test_empty_array_valid(self):
        """Test that empty array passes validation (validated at runtime in R)."""
        schema = table_schema()
        data = []
        # Empty array passes JSON Schema but R will validate at runtime
        validate(instance=data, schema=schema)

    def test_mixed_types_in_column(self):
        """Test column with mixed types (allowed by schema, handled at runtime)."""
        schema = table_schema()
        # JSON Schema allows mixed types in arrays by default
        data = {"col1": [1, "two", 3.0]}
        # This may pass JSON Schema but R will handle type coercion
        validate(instance=data, schema=schema)

    def test_nested_arrays_in_column_oriented(self):
        """Test that column values are arrays."""
        schema = table_schema()
        data = {"col1": [1, 2, 3], "col2": [[1, 2], [3, 4]]}
        # Nested arrays are allowed by schema, R handles the structure
        validate(instance=data, schema=schema)

    def test_row_objects_with_various_types(self):
        """Test row-oriented data with various value types."""
        schema = table_schema()
        data = [
            {"name": "Alice", "age": 30, "active": True},
            {"name": "Bob", "age": 25, "active": False},
        ]
        validate(instance=data, schema=schema)

    def test_null_value_in_column(self):
        """Test that null values in columns are allowed (represents NA in R)."""
        schema = table_schema()
        data = {"col1": [1, None, 3], "col2": [4, 5, None]}
        validate(instance=data, schema=schema)

    def test_null_value_in_row(self):
        """Test that null values in rows are allowed."""
        schema = table_schema()
        data = [
            {"col1": 1, "col2": None},
            {"col1": None, "col2": 5},
        ]
        validate(instance=data, schema=schema)

    def test_string_not_valid(self):
        """Test that a plain string is rejected."""
        schema = table_schema()
        data = "not a table"
        with pytest.raises(ValidationError):
            validate(instance=data, schema=schema)

    def test_number_not_valid(self):
        """Test that a plain number is rejected."""
        schema = table_schema()
        data = 42
        with pytest.raises(ValidationError):
            validate(instance=data, schema=schema)


class TestTableSchemaDescription:
    """Test table_schema metadata."""

    def test_has_description(self):
        """Test that schema has a description."""
        schema = table_schema()
        assert "description" in schema
        assert "column-oriented" in schema["description"]
        assert "row-oriented" in schema["description"]

    def test_accepts_both_types(self):
        """Test that schema type allows both object and array."""
        schema = table_schema()
        assert "type" in schema
        type_value = schema["type"]
        # Type can be list or single value
        if isinstance(type_value, list):
            assert "object" in type_value
            assert "array" in type_value
        else:
            # If single type, it should work with our data
            assert type_value in ["object", "array"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
