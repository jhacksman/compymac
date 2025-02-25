import pytest
import pytest_asyncio
import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from desktop_automation import DesktopAutomation

@pytest_asyncio.fixture(scope="function")
async def automation():
    """Create automation fixture."""
    automation = DesktopAutomation()
    try:
        await automation.start()
        yield automation
    finally:
        try:
            await automation.stop()
        except Exception:
            pass

@pytest.fixture
def test_dir(tmp_path):
    """Create a temporary directory for testing."""
    return str(tmp_path)

@pytest.mark.asyncio
async def test_create_folder(automation, test_dir):
    """Test creating a new folder."""
    new_folder = os.path.join(test_dir, "test_folder")
    success = await automation.create_folder(new_folder)
    assert success is True
    assert os.path.exists(new_folder)
    assert os.path.isdir(new_folder)

@pytest.mark.asyncio
async def test_move_items(automation, test_dir):
    """Test moving files between directories."""
    # Create source and destination folders
    source_dir = os.path.join(test_dir, "source")
    dest_dir = os.path.join(test_dir, "destination")
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(dest_dir, exist_ok=True)
    
    # Create a test file
    test_file = os.path.join(source_dir, "test.txt")
    with open(test_file, "w") as f:
        f.write("test content")
    
    # Move the file
    success = await automation.move_items([test_file], dest_dir)
    assert success
    assert not os.path.exists(test_file)
    assert os.path.exists(os.path.join(dest_dir, "test.txt"))

@pytest.mark.asyncio
async def test_move_items_permission_denied(automation, test_dir):
    """Test moving files with insufficient permissions."""
    # Create source and destination with restricted permissions
    source_dir = os.path.join(test_dir, "restricted_source")
    dest_dir = os.path.join(test_dir, "restricted_dest")
    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(dest_dir, exist_ok=True)
    
    # Create a test file
    test_file = os.path.join(source_dir, "test.txt")
    with open(test_file, "w") as f:
        f.write("test content")
    
    # Remove write permission from destination
    os.chmod(dest_dir, 0o444)
    
    # Attempt to move file
    success = await automation.move_items([test_file], dest_dir)
    assert not success
    assert os.path.exists(test_file)

@pytest.mark.asyncio
async def test_get_selected_items(automation):
    """Test getting selected items from Finder.
    Note: This test requires manual verification as it depends on Finder's UI state.
    """
    items = await automation.get_selected_items()
    assert isinstance(items, list)
    # Note: Cannot assert specific items as they depend on Finder's state
