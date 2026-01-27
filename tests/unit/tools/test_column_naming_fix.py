import pytest
from rmcp.tools.helpers import suggest_fix

@pytest.mark.asyncio
async def test_suggest_fix_column_with_special_chars():
    """Test that suggest_fix recommends backticks for column names with special characters."""
    error_message = "Error in summarise(): ! object 'Credit (Revenue)' not found"
    params = {
        "error_message": error_message,
        "tool_name": "execute_r_analysis"
    }
    
    # Mocking context is not strictly necessary for this test as suggest_fix 
    # only uses it for logging which we can ignore for this unit test
    class MockContext:
        async def info(self, *args, **kwargs): pass
        async def error(self, *args, **kwargs): pass
    
    result = await suggest_fix(MockContext(), params)
    
    assert result["error_type"] == "missing_variable"
    # Check if the backtick suggestion is present
    found_backtick_suggestion = any(
        "backticks" in s and "Credit (Revenue)" in s 
        for s in result["suggestions"]
    )
    assert found_backtick_suggestion, "Backtick suggestion not found in suggestions"

@pytest.mark.asyncio
async def test_suggest_fix_formula_syntax_update():
    """Test that suggest_fix's formula syntax suggestion mentions backticks."""
    error_message = "Error: invalid formula"
    params = {
        "error_message": error_message
    }
    
    class MockContext:
        async def info(self, *args, **kwargs): pass
    
    result = await suggest_fix(MockContext(), params)
    
    assert result["error_type"] == "formula_syntax"
    found_backtick_mention = any(
        "backticks" in s and "Variable Name" in s 
        for s in result["suggestions"]
    )
    assert found_backtick_mention, "Backtick mention not found in formula syntax suggestions"
