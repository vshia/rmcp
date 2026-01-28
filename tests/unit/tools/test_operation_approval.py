"""
Unit tests for the universal operation approval system.
Tests the approve_operation tool and validation logic.
"""

import pytest
from rmcp.core.context import Context, LifespanState
from rmcp.security.vfs import VFS
from rmcp.tools.flexible_r import (
    OPERATION_CATEGORIES,
    approve_operation,
    auto_approve_exports_operations,
    is_operation_approved,
    rewrite_file_paths_to_exports,
    validate_r_code,
)


@pytest.fixture
async def mock_context():
    """Create a mock context for testing."""
    lifespan = LifespanState()
    context = Context.create("test", "test", lifespan)
    return context


class TestOperationApproval:
    """Test the approve_operation tool functionality."""

    @pytest.mark.asyncio
    async def test_approve_file_operation(self, mock_context):
        """Test approving file operations."""
        params = {
            "operation_type": "file_operations",
            "specific_operation": "ggsave",
            "action": "approve",
            "scope": "session",
            "directory": "./plots",
        }

        result = await approve_operation(mock_context, params)

        assert result["success"] is True
        assert result["action"] == "approved"
        assert result["operation_type"] == "file_operations"
        assert result["specific_operation"] == "ggsave"
        assert "approved_operations" in result
        assert "security_info" in result

    @pytest.mark.asyncio
    async def test_approve_package_installation(self, mock_context):
        """Test approving package installation."""
        params = {
            "operation_type": "package_installation",
            "specific_operation": "install.packages",
            "action": "approve",
            "scope": "session",
        }

        result = await approve_operation(mock_context, params)

        assert result["success"] is True
        assert result["action"] == "approved"
        assert result["operation_type"] == "package_installation"
        assert result["specific_operation"] == "install.packages"

    @pytest.mark.asyncio
    async def test_deny_operation(self, mock_context):
        """Test denying operations."""
        params = {
            "operation_type": "system_operations",
            "specific_operation": "system",
            "action": "deny",
        }

        result = await approve_operation(mock_context, params)

        assert result["success"] is True
        assert result["action"] == "denied"
        assert result["scope"] == "none"

    @pytest.mark.asyncio
    async def test_session_approval_tracking(self, mock_context):
        """Test that approvals are tracked in session context."""
        # Approve file operations
        await approve_operation(
            mock_context,
            {
                "operation_type": "file_operations",
                "specific_operation": "ggsave",
                "action": "approve",
            },
        )

        # Check that approval is tracked
        assert hasattr(mock_context, "_approved_operations")
        assert "file_operations" in mock_context._approved_operations
        assert "ggsave" in mock_context._approved_operations["file_operations"]

    def test_is_operation_approved_logic(self, mock_context):
        """Test the operation approval checking logic."""
        # Initially not approved
        assert not is_operation_approved(mock_context, "file_operations", "ggsave")

        # Add approval manually
        mock_context._approved_operations = {
            "file_operations": {"ggsave": {"approved_at": 123456}}
        }

        # Now should be approved
        assert is_operation_approved(mock_context, "file_operations", "ggsave")
        assert not is_operation_approved(mock_context, "file_operations", "write.csv")


class TestValidationWithApproval:
    """Test R code validation with the approval system."""

    def test_validation_requires_approval_for_ggsave(self):
        """Test that ggsave requires approval."""
        r_code = 'ggsave("plot.png", plot = p)'
        is_safe, error = validate_r_code(r_code)

        assert not is_safe
        assert "OPERATION_APPROVAL_NEEDED:file_operations:ggsave" in error

    def test_validation_requires_approval_for_install_packages(self):
        """Test that install.packages requires approval."""
        r_code = 'install.packages("moments")'
        is_safe, error = validate_r_code(r_code)

        assert not is_safe
        assert (
            "OPERATION_APPROVAL_NEEDED:package_installation:install.packages" in error
        )

    def test_validation_allows_approved_operations(self, mock_context):
        """Test that approved operations pass validation."""
        # Add approval
        mock_context._approved_operations = {
            "file_operations": {"ggsave": {"approved_at": 123456}}
        }

        r_code = 'ggsave("plot.png", plot = p)'
        is_safe, error = validate_r_code(r_code, context=mock_context)

        assert is_safe
        assert error is None

    def test_validation_still_blocks_dangerous_patterns(self, mock_context):
        """Test that truly dangerous patterns are still blocked."""
        r_code = 'system("rm -rf /")'
        is_safe, error = validate_r_code(r_code, context=mock_context)

        assert not is_safe
        assert "OPERATION_APPROVAL_NEEDED:system_operations:system" in error

    def test_validation_blocks_non_approvable_dangerous_patterns(self):
        """Test that some dangerous patterns cannot be approved."""
        r_code = 'setwd("/etc")'
        is_safe, error = validate_r_code(r_code)

        assert not is_safe
        assert "Dangerous pattern detected" in error


class TestOperationCategories:
    """Test the operation category configuration."""

    def test_operation_categories_structure(self):
        """Test that operation categories are properly structured."""
        assert "file_operations" in OPERATION_CATEGORIES
        assert "package_installation" in OPERATION_CATEGORIES
        assert "system_operations" in OPERATION_CATEGORIES

        for _category, config in OPERATION_CATEGORIES.items():
            assert "patterns" in config
            assert "description" in config
            assert "examples" in config
            assert "security_level" in config
            assert isinstance(config["patterns"], list)
            assert len(config["patterns"]) > 0

    def test_file_operations_patterns(self):
        """Test that file operation patterns are correct."""
        patterns = OPERATION_CATEGORIES["file_operations"]["patterns"]
        assert any("ggsave" in pattern for pattern in patterns)
        assert any("write\\.csv" in pattern for pattern in patterns)
        assert any("writeLines" in pattern for pattern in patterns)

    def test_package_installation_patterns(self):
        """Test that package installation patterns are correct."""
        patterns = OPERATION_CATEGORIES["package_installation"]["patterns"]
        assert any("install\\.packages" in pattern for pattern in patterns)

    def test_system_operations_patterns(self):
        """Test that system operation patterns are correct."""
        patterns = OPERATION_CATEGORIES["system_operations"]["patterns"]
        assert any("system" in pattern for pattern in patterns)
        assert any("shell" in pattern for pattern in patterns)
        assert any("Sys\\.setenv" in pattern for pattern in patterns)


class TestAutoApprovalForExports:
    """Test automatic approval for exports directory operations."""

    @pytest.fixture
    def mock_context_with_vfs(self, tmp_path):
        """Create a mock context with VFS initialized."""
        lifespan = LifespanState()
        lifespan.vfs = VFS(allowed_roots=[tmp_path], read_only=True)
        context = Context.create("test", "test", lifespan)
        return context

    def test_auto_approve_ggsave_to_exports(self, mock_context_with_vfs):
        """Test that ggsave targeting exports directory is auto-approved."""
        r_code = 'ggsave("exports/plot.png", plot = p)'

        # Should not be approved initially
        assert not is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should now be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")
        assert hasattr(mock_context_with_vfs, "_approved_operations")
        assert "file_operations" in mock_context_with_vfs._approved_operations
        assert "ggsave" in mock_context_with_vfs._approved_operations["file_operations"]

        # Check auto-approval flag
        approval_data = mock_context_with_vfs._approved_operations["file_operations"]["ggsave"]
        assert approval_data.get("auto_approved") is True
        assert approval_data.get("directory") == "./exports"

    def test_auto_approve_write_csv_to_exports(self, mock_context_with_vfs):
        """Test that write.csv targeting exports directory is auto-approved."""
        r_code = 'write.csv(data, "exports/data.csv")'

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "write.csv")

    def test_auto_approve_with_relative_exports_path(self, mock_context_with_vfs):
        """Test that ./exports/ path is also auto-approved."""
        r_code = 'ggsave("./exports/plot.png", plot = p)'

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")

    def test_no_auto_approve_for_non_exports_paths(self, mock_context_with_vfs):
        """Test that file operations are auto-approved (since all paths go to exports after rewriting)."""
        r_code = 'ggsave("/tmp/plot.png", plot = p)'

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should BE approved since path rewriting sends all operations to exports
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")

    def test_vfs_write_mode_enabled_on_auto_approve(self, mock_context_with_vfs):
        """Test that VFS read-only mode is disabled on auto-approval."""
        r_code = 'ggsave("exports/plot.png", plot = p)'

        # VFS should start in read-only mode
        assert mock_context_with_vfs.lifespan.vfs.read_only is True

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # VFS should now be in write mode
        assert mock_context_with_vfs.lifespan.vfs.read_only is False

    def test_exports_directory_added_to_vfs_roots(self, mock_context_with_vfs, tmp_path):
        """Test that exports directory is added to VFS allowed roots."""
        import os

        # Change to a temporary directory for this test
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            r_code = 'ggsave("exports/plot.png", plot = p)'

            # Run auto-approval
            auto_approve_exports_operations(mock_context_with_vfs, r_code)

            # Check that exports directory is in allowed roots
            exports_path = (tmp_path / "exports").resolve()
            vfs_roots = [root.resolve() for root in mock_context_with_vfs.lifespan.vfs.allowed_roots]
            assert exports_path in vfs_roots
        finally:
            os.chdir(original_cwd)

    def test_validation_passes_with_auto_approval(self, mock_context_with_vfs):
        """Test that validation passes for exports operations after auto-approval."""
        r_code = 'ggsave("exports/plot.png", plot = p)'

        # Validation should trigger auto-approval
        is_safe, error = validate_r_code(r_code, context=mock_context_with_vfs)

        # Should be safe after auto-approval
        assert is_safe
        assert error is None
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")

    def test_multiple_file_operations_auto_approved(self, mock_context_with_vfs):
        """Test that multiple file operation types are auto-approved."""
        r_code = '''
        ggsave("exports/plot.png", plot = p)
        write.csv(data, "exports/data.csv")
        writeLines(text, "exports/text.txt")
        '''

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # All should be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "write.csv")
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "writeLines")

    def test_auto_approve_no_context(self):
        """Test that auto-approval handles None context gracefully."""
        r_code = 'ggsave("exports/plot.png", plot = p)'

        # Should not raise an error
        auto_approve_exports_operations(None, r_code)

    def test_auto_approve_no_vfs(self):
        """Test that auto-approval works without VFS."""
        lifespan = LifespanState()
        context = Context.create("test", "test", lifespan)

        r_code = 'ggsave("exports/plot.png", plot = p)'

        # Should not raise an error
        auto_approve_exports_operations(context, r_code)

        # Approval should still be recorded
        assert is_operation_approved(context, "file_operations", "ggsave")

    def test_auto_approve_with_named_parameter(self, mock_context_with_vfs):
        """Test that ggsave with named parameter is auto-approved."""
        r_code = 'ggsave(filename = "exports/plot.png", plot = p, width = 8, height = 5)'

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")

    def test_auto_approve_with_parameter_order(self, mock_context_with_vfs):
        """Test that ggsave with filename not first is auto-approved."""
        r_code = 'ggsave(plot = p, filename = "exports/plot.png", width = 8)'

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")

    def test_auto_approve_with_session_subdirectory(self, mock_context_with_vfs):
        """Test that exports with session subdirectory is auto-approved."""
        r_code = 'ggsave("exports/session_abc123/plot.png", plot = p)'

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "ggsave")

    def test_auto_approve_excel_files(self, mock_context_with_vfs):
        """Test that Excel file operations to exports are auto-approved."""
        r_code = 'write.xlsx(data, "exports/data.xlsx")'

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "write.xlsx")

    def test_auto_approve_saveRDS(self, mock_context_with_vfs):
        """Test that saveRDS to exports is auto-approved."""
        r_code = 'saveRDS(model, file = "exports/model.rds")'

        # Run auto-approval
        auto_approve_exports_operations(mock_context_with_vfs, r_code)

        # Should be approved
        assert is_operation_approved(mock_context_with_vfs, "file_operations", "saveRDS")


class TestFilePathRewriting:
    """Test automatic file path rewriting to exports directory."""

    @pytest.fixture
    def mock_context_with_session(self):
        """Create a mock context with session ID."""
        lifespan = LifespanState()
        context = Context.create("test", "test", lifespan)
        # Set session ID in metadata
        context.request.metadata = {"mcp_session_id": "test_session_123"}
        return context

    def test_rewrite_ggsave_absolute_path(self, mock_context_with_session):
        """Test rewriting absolute path in ggsave."""
        r_code = 'ggsave("/mnt/data/plot.png", plot = p)'

        rewritten = rewrite_file_paths_to_exports(mock_context_with_session, r_code)

        # Should convert to relative path (working directory will be set to exports/{session_id}/)
        assert 'mnt/data/plot.png' in rewritten
        assert rewritten == 'ggsave("mnt/data/plot.png", plot = p)'

    def test_rewrite_ggsave_with_filename_param(self, mock_context_with_session):
        """Test rewriting ggsave with filename parameter."""
        r_code = 'ggsave(filename = "/tmp/revenue.png", plot = p, width = 8)'

        rewritten = rewrite_file_paths_to_exports(mock_context_with_session, r_code)

        assert 'tmp/revenue.png' in rewritten
        assert rewritten == 'ggsave(filename = "tmp/revenue.png", plot = p, width = 8)'

    def test_rewrite_write_csv(self, mock_context_with_session):
        """Test rewriting write.csv path."""
        r_code = 'write.csv(data, "/var/tmp/data.csv")'

        rewritten = rewrite_file_paths_to_exports(mock_context_with_session, r_code)

        assert 'var/tmp/data.csv' in rewritten
        assert rewritten == 'write.csv(data, "var/tmp/data.csv")'

    def test_rewrite_write_xlsx(self, mock_context_with_session):
        """Test rewriting write.xlsx path."""
        r_code = 'write.xlsx(df, file = "/output/report.xlsx")'

        rewritten = rewrite_file_paths_to_exports(mock_context_with_session, r_code)

        assert 'output/report.xlsx' in rewritten
        assert rewritten == 'write.xlsx(df, file = "output/report.xlsx")'

    def test_rewrite_multiple_operations(self, mock_context_with_session):
        """Test rewriting multiple file operations."""
        r_code = '''
        ggsave("/tmp/plot.png", p)
        write.csv(data, "/tmp/data.csv")
        saveRDS(model, "/tmp/model.rds")
        '''

        rewritten = rewrite_file_paths_to_exports(mock_context_with_session, r_code)

        assert 'tmp/plot.png' in rewritten
        assert 'tmp/data.csv' in rewritten
        assert 'tmp/model.rds' in rewritten
        assert '"/tmp/' not in rewritten  # Check for quoted /tmp/ paths

    def test_preserve_relative_paths(self, mock_context_with_session):
        """Test that relative paths (no leading slash) are not modified."""
        r_code = 'ggsave("relative/path/plot.png", plot = p)'

        rewritten = rewrite_file_paths_to_exports(mock_context_with_session, r_code)

        # Should remain unchanged since it's already relative
        assert rewritten == r_code
        assert 'relative/path/plot.png' in rewritten

    def test_leading_slash_removal(self, mock_context_with_session):
        """Test that leading slashes are removed from absolute paths."""
        r_code = 'ggsave("//data//plot.png", plot = p)'

        rewritten = rewrite_file_paths_to_exports(mock_context_with_session, r_code)

        # Should strip all leading slashes, resulting in relative path
        assert 'data//plot.png' in rewritten or 'data/plot.png' in rewritten
        assert not rewritten.startswith('ggsave("/')  # No leading slash

    def test_no_context(self):
        """Test that rewriting handles None context gracefully."""
        r_code = 'ggsave("/tmp/plot.png", plot = p)'

        rewritten = rewrite_file_paths_to_exports(None, r_code)

        # Should return unchanged
        assert rewritten == r_code

    def test_no_session_id_still_rewrites(self):
        """Test that path rewriting works even without session ID (for logging only)."""
        lifespan = LifespanState()
        context = Context.create("test", "test", lifespan)
        # No session ID set

        r_code = 'ggsave("/tmp/plot.png", plot = p)'
        rewritten = rewrite_file_paths_to_exports(context, r_code)

        # Should still convert to relative path
        assert 'tmp/plot.png' in rewritten
        assert rewritten == 'ggsave("tmp/plot.png", plot = p)'

    def test_complex_path_preservation(self, mock_context_with_session):
        """Test preserving full path structure from complex nested path."""
        r_code = 'ggsave("/very/deep/nested/path/to/file.png", plot = p)'

        rewritten = rewrite_file_paths_to_exports(mock_context_with_session, r_code)

        # Should preserve full path structure as relative path
        assert 'very/deep/nested/path/to/file.png' in rewritten
        assert rewritten == 'ggsave("very/deep/nested/path/to/file.png", plot = p)'
        assert '"/very/deep/nested/' not in rewritten  # Original absolute path should be replaced
