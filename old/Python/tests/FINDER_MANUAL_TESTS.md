# Manual Test Cases for Finder Automation

## File System Operations
1. Create Folder
   - Use the app to create a new folder
   - Verify that:
     * Folder appears in Finder
     * Folder name is correct
     * Folder permissions are correct

2. Move Items
   - Select multiple files in Finder
   - Use the app to move them to a new location
   - Verify that:
     * Files disappear from source
     * Files appear at destination
     * File contents remain intact
     * File metadata is preserved

3. Permission Handling
   - Try to create folder in restricted location
   - Try to move files to restricted location
   - Verify that:
     * Appropriate error messages are shown
     * App remains stable
     * Original files are unaffected

## Finder Integration
1. Selection Handling
   - Select items in Finder
   - Use app to get selected items
   - Verify that:
     * All selected items are reported
     * Paths are correct
     * Selection updates in real-time

2. Visual Feedback
   - Perform file operations
   - Verify that:
     * Finder windows update immediately
     * Visual feedback matches operation
     * No UI glitches occur

## Error Recovery
1. Invalid Operations
   - Try operations with invalid paths
   - Attempt operations on locked files
   - Verify that:
     * Error messages are clear
     * System remains stable
     * Recovery options are provided

## Performance
1. Bulk Operations
   - Test with large number of files
   - Test with deep directory structures
   - Verify that:
     * Operations complete in reasonable time
     * Memory usage remains stable
     * UI remains responsive
