"""
Tests for the hierarchical tool menu system.

Tests cover:
- ToolMode dataclass
- MenuManager state machine
- Mode navigation (enter, exit, list)
- Tool visibility per mode
- Integration with LocalHarness
"""

from compymac.local_harness import LocalHarness
from compymac.tool_menu import (
    META_TOOLS,
    TOOL_MODES,
    MenuManager,
    MenuState,
    ToolMode,
)


class TestToolMode:
    """Tests for the ToolMode dataclass."""

    def test_tool_mode_creation(self):
        """Test creating a ToolMode with all fields."""
        mode = ToolMode(
            name="test",
            display_name="Test Mode",
            tool_list=["tool1", "tool2"],
            description="A test mode",
        )
        assert mode.name == "test"
        assert mode.display_name == "Test Mode"
        assert mode.tool_list == ["tool1", "tool2"]
        assert mode.description == "A test mode"

    def test_predefined_modes_exist(self):
        """Test that all predefined modes are defined."""
        expected_modes = ["swe", "browser", "git", "deploy", "search", "ai", "data"]
        for mode_name in expected_modes:
            assert mode_name in TOOL_MODES, f"Mode '{mode_name}' not found in TOOL_MODES"

    def test_swe_mode_tools(self):
        """Test that SWE mode has the expected tools."""
        swe_mode = TOOL_MODES["swe"]
        expected_tools = [
            "Read", "Edit", "Write", "bash", "grep", "glob",
            "lsp_tool", "git_status", "git_diff_unstaged", "git_diff_staged",
            "git_commit", "git_add",
            "web_search", "web_get_contents",  # Research capabilities
        ]
        assert swe_mode.tool_list == expected_tools
        assert len(swe_mode.tool_list) == 14  # 12 core + 2 research tools

    def test_browser_mode_tools(self):
        """Test that browser mode has the expected tools."""
        browser_mode = TOOL_MODES["browser"]
        assert len(browser_mode.tool_list) == 9
        assert "browser_navigate" in browser_mode.tool_list
        assert "browser_view" in browser_mode.tool_list

    def test_git_mode_tools(self):
        """Test that git mode has both local and remote tools."""
        git_mode = TOOL_MODES["git"]
        # Local tools
        assert "git_status" in git_mode.tool_list
        assert "git_commit" in git_mode.tool_list
        # Remote tools
        assert "git_view_pr" in git_mode.tool_list
        assert "git_create_pr" in git_mode.tool_list

    def test_deploy_mode_tools(self):
        """Test that deploy mode has the expected tools."""
        deploy_mode = TOOL_MODES["deploy"]
        assert len(deploy_mode.tool_list) == 3
        assert "deploy" in deploy_mode.tool_list

    def test_search_mode_tools(self):
        """Test that search mode has the expected tools."""
        search_mode = TOOL_MODES["search"]
        assert len(search_mode.tool_list) == 4
        assert "web_search" in search_mode.tool_list
        assert "browser_navigate" in search_mode.tool_list  # Cross-mode tool

    def test_ai_mode_tools(self):
        """Test that AI mode has the expected tools."""
        ai_mode = TOOL_MODES["ai"]
        assert len(ai_mode.tool_list) == 4
        assert "ask_smart_friend" in ai_mode.tool_list
        assert "visual_checker" in ai_mode.tool_list

    def test_data_mode_tools(self):
        """Test that data mode has filesystem tools."""
        data_mode = TOOL_MODES["data"]
        assert len(data_mode.tool_list) == 7
        assert "fs_read_file" in data_mode.tool_list


class TestMenuManager:
    """Tests for the MenuManager class."""

    def test_initial_state_is_root(self):
        """Test that MenuManager starts at ROOT."""
        manager = MenuManager()
        assert manager.is_at_root()
        assert manager.current_mode is None
        assert manager.state == MenuState.ROOT

    def test_enter_valid_mode(self):
        """Test entering a valid mode."""
        manager = MenuManager()
        success, message = manager.enter_mode("swe")
        assert success
        assert "Entered Software Engineering" in message
        assert manager.current_mode == "swe"
        assert manager.state == MenuState.IN_MODE
        assert not manager.is_at_root()

    def test_enter_invalid_mode(self):
        """Test entering an invalid mode fails gracefully."""
        manager = MenuManager()
        success, message = manager.enter_mode("invalid_mode")
        assert not success
        assert "Unknown mode" in message
        assert manager.is_at_root()

    def test_exit_mode(self):
        """Test exiting a mode returns to ROOT."""
        manager = MenuManager()
        manager.enter_mode("swe")
        success, message = manager.exit_mode()
        assert success
        assert "Exited swe mode" in message
        assert manager.is_at_root()
        assert manager.current_mode is None

    def test_exit_at_root_fails(self):
        """Test that exiting at ROOT fails gracefully."""
        manager = MenuManager()
        success, message = manager.exit_mode()
        assert not success
        assert "Already at ROOT" in message

    def test_get_current_mode(self):
        """Test getting the current ToolMode object."""
        manager = MenuManager()
        assert manager.get_current_mode() is None

        manager.enter_mode("browser")
        mode = manager.get_current_mode()
        assert mode is not None
        assert mode.name == "browser"
        assert mode.display_name == "Browser Automation"

    def test_get_visible_tools_at_root(self):
        """Test that only meta-tools are visible at ROOT."""
        manager = MenuManager()
        visible = manager.get_visible_tools()
        assert set(visible) == set(META_TOOLS)

    def test_get_visible_tools_in_mode(self):
        """Test that meta-tools + mode tools are visible in a mode."""
        manager = MenuManager()
        manager.enter_mode("swe")
        visible = manager.get_visible_tools()

        # Should include all meta-tools
        for meta_tool in META_TOOLS:
            assert meta_tool in visible

        # Should include SWE mode tools
        swe_tools = TOOL_MODES["swe"].tool_list
        for tool in swe_tools:
            assert tool in visible

        # Total should be meta-tools + SWE tools
        expected_count = len(META_TOOLS) + len(swe_tools)
        assert len(visible) == expected_count

    def test_swe_mode_has_18_tools(self):
        """Test that SWE mode has exactly 18 tools (12 swe + 6 meta)."""
        manager = MenuManager()
        manager.enter_mode("swe")
        visible = manager.get_visible_tools()
        assert len(visible) == 20  # 14 SWE tools + 6 meta-tools

    def test_list_menu_at_root(self):
        """Test list_menu output at ROOT."""
        manager = MenuManager()
        output = manager.list_menu()
        assert "ROOT" in output
        assert "Available modes:" in output
        assert "swe:" in output
        assert "browser:" in output
        assert "menu_enter" in output

    def test_list_menu_in_mode(self):
        """Test list_menu output in a mode."""
        manager = MenuManager()
        manager.enter_mode("swe")
        output = manager.list_menu()
        assert "Software Engineering" in output
        assert "Available tools" in output
        assert "Read" in output
        assert "Edit" in output
        assert "Meta-tools" in output
        assert "menu_exit" in output

    def test_get_available_modes(self):
        """Test getting list of available modes."""
        manager = MenuManager()
        modes = manager.get_available_modes()
        assert "swe" in modes
        assert "browser" in modes
        assert "git" in modes
        assert "deploy" in modes
        assert "search" in modes
        assert "ai" in modes
        assert "data" in modes

    def test_reset(self):
        """Test resetting the menu to ROOT."""
        manager = MenuManager()
        manager.enter_mode("browser")
        assert not manager.is_at_root()

        manager.reset()
        assert manager.is_at_root()
        assert manager.current_mode is None

    def test_mode_switching(self):
        """Test switching between modes."""
        manager = MenuManager()

        # Enter SWE mode
        manager.enter_mode("swe")
        assert manager.current_mode == "swe"

        # Exit and enter browser mode
        manager.exit_mode()
        manager.enter_mode("browser")
        assert manager.current_mode == "browser"

        # Direct switch (enter while in mode)
        manager.enter_mode("git")
        assert manager.current_mode == "git"


class TestMetaTools:
    """Tests for meta-tools configuration."""

    def test_meta_tools_list(self):
        """Test that META_TOOLS contains expected tools."""
        expected = [
            "menu_list",
            "menu_enter",
            "menu_exit",
            "complete",
            "think",
            "message_user",
        ]
        assert META_TOOLS == expected

    def test_meta_tools_count(self):
        """Test that there are exactly 6 meta-tools."""
        assert len(META_TOOLS) == 6


class TestLocalHarnessIntegration:
    """Tests for LocalHarness integration with menu system."""

    def test_harness_has_menu_manager(self):
        """Test that LocalHarness has a MenuManager."""
        harness = LocalHarness()
        assert hasattr(harness, '_menu_manager')
        assert isinstance(harness._menu_manager, MenuManager)

    def test_harness_menu_tools_registered(self):
        """Test that menu navigation tools are registered."""
        harness = LocalHarness()
        assert "menu_list" in harness._tools
        assert "menu_enter" in harness._tools
        assert "menu_exit" in harness._tools

    def test_menu_list_tool(self):
        """Test the menu_list tool handler."""
        harness = LocalHarness()
        result = harness._menu_list()
        assert "ROOT" in result
        assert "Available modes:" in result

    def test_menu_enter_tool(self):
        """Test the menu_enter tool handler."""
        harness = LocalHarness()
        result = harness._menu_enter("swe")
        assert "Entered Software Engineering" in result
        assert harness._menu_manager.current_mode == "swe"

    def test_menu_exit_tool(self):
        """Test the menu_exit tool handler."""
        harness = LocalHarness()
        harness._menu_enter("swe")
        result = harness._menu_exit()
        assert "Exited" in result
        assert harness._menu_manager.is_at_root()

    def test_get_menu_tool_schemas_at_root(self):
        """Test get_menu_tool_schemas at ROOT returns only meta-tools."""
        harness = LocalHarness()
        schemas = harness.get_menu_tool_schemas()

        # Should only have meta-tools
        tool_names = [s["function"]["name"] for s in schemas]
        assert len(tool_names) == len(META_TOOLS)
        for meta_tool in META_TOOLS:
            assert meta_tool in tool_names

    def test_get_menu_tool_schemas_in_swe_mode(self):
        """Test get_menu_tool_schemas in SWE mode returns 20 tools."""
        harness = LocalHarness()
        harness._menu_enter("swe")
        schemas = harness.get_menu_tool_schemas()

        tool_names = [s["function"]["name"] for s in schemas]
        # 14 SWE tools + 6 meta-tools = 20
        assert len(tool_names) == 20

        # Check meta-tools are present
        for meta_tool in META_TOOLS:
            assert meta_tool in tool_names

        # Check SWE tools are present
        for swe_tool in TOOL_MODES["swe"].tool_list:
            assert swe_tool in tool_names

    def test_get_menu_manager(self):
        """Test get_menu_manager returns the menu manager."""
        harness = LocalHarness()
        manager = harness.get_menu_manager()
        assert manager is harness._menu_manager

    def test_reset_menu(self):
        """Test reset_menu resets to ROOT."""
        harness = LocalHarness()
        harness._menu_enter("browser")
        assert not harness._menu_manager.is_at_root()

        harness.reset_menu()
        assert harness._menu_manager.is_at_root()

    def test_menu_system_reduces_context(self):
        """Test that menu system significantly reduces tool count."""
        harness = LocalHarness()

        # All tools (without menu system)
        all_schemas = harness.get_tool_schemas()
        all_count = len(all_schemas)

        # Menu tools at ROOT
        menu_schemas = harness.get_menu_tool_schemas()
        menu_count = len(menu_schemas)

        # Menu system should expose far fewer tools
        assert menu_count < all_count
        assert menu_count == 6  # Only meta-tools at ROOT

    def test_cross_mode_tools_work(self):
        """Test that cross-mode tools work when registered.

        Note: browser_navigate is in search mode's tool_list, but it only
        appears in schemas if browser tools are registered via register_browser_tools().
        This test verifies that web_search (always registered) is available in search mode.
        """
        harness = LocalHarness()
        harness._menu_enter("search")
        schemas = harness.get_menu_tool_schemas()

        tool_names = [s["function"]["name"] for s in schemas]
        # web_search should be in search mode
        assert "web_search" in tool_names
        assert "web_get_contents" in tool_names

    def test_cross_mode_browser_tools_when_registered(self):
        """Test that browser tools appear in search mode when registered."""
        harness = LocalHarness()
        harness.register_browser_tools()  # Register browser tools
        harness._menu_enter("search")
        schemas = harness.get_menu_tool_schemas()

        tool_names = [s["function"]["name"] for s in schemas]
        # browser_navigate should now be in search mode
        assert "browser_navigate" in tool_names
        assert "browser_view" in tool_names
        assert "web_search" in tool_names


class TestAgentConfigIntegration:
    """Tests for AgentConfig integration with menu system."""

    def test_use_menu_system_flag_exists(self):
        """Test that use_menu_system flag exists in AgentConfig."""
        from compymac.agent_loop import AgentConfig
        config = AgentConfig()
        assert hasattr(config, 'use_menu_system')
        assert config.use_menu_system is False  # Default is False

    def test_use_menu_system_can_be_enabled(self):
        """Test that use_menu_system can be enabled."""
        from compymac.agent_loop import AgentConfig
        config = AgentConfig(use_menu_system=True)
        assert config.use_menu_system is True
