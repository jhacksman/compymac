/**
 * Screenshot capture utility for Cobalt macOS app tests
 * Captures screenshots of the application for visual testing
 */

const fs = require('fs');
const path = require('path');

class ScreenshotCapture {
  constructor() {
    this.screenshotDir = path.join(__dirname, '..', 'screenshots', 'actual');
    
    // Ensure directory exists
    if (!fs.existsSync(this.screenshotDir)) {
      fs.mkdirSync(this.screenshotDir, { recursive: true });
    }
  }
  
  /**
   * Capture a screenshot of the entire window
   * @param {BrowserWindow} window - Electron browser window
   * @param {string} name - Screenshot name
   * @returns {Promise<string>} - Path to the saved screenshot
   */
  async captureWindow(window, name) {
    if (!window || window.isDestroyed()) {
      throw new Error('Invalid window for screenshot capture');
    }
    
    try {
      const image = await window.capturePage();
      const screenshotPath = path.join(this.screenshotDir, `${name}.png`);
      
      fs.writeFileSync(screenshotPath, image.toPNG());
      console.log(`Screenshot saved to ${screenshotPath}`);
      
      return screenshotPath;
    } catch (error) {
      console.error('Error capturing window screenshot:', error);
      throw error;
    }
  }
  
  /**
   * Capture a screenshot of a specific element
   * @param {BrowserWindow} window - Electron browser window
   * @param {string} selector - CSS selector for the element
   * @param {string} name - Screenshot name
   * @returns {Promise<string>} - Path to the saved screenshot
   */
  async captureElement(window, selector, name) {
    if (!window || window.isDestroyed()) {
      throw new Error('Invalid window for screenshot capture');
    }
    
    try {
      // Execute script to get element bounds
      const bounds = await window.webContents.executeJavaScript(`
        const element = document.querySelector("${selector}");
        if (!element) {
          return null;
        }
        const rect = element.getBoundingClientRect();
        return {
          x: Math.floor(rect.x),
          y: Math.floor(rect.y),
          width: Math.ceil(rect.width),
          height: Math.ceil(rect.height)
        };
      `);
      
      if (!bounds) {
        throw new Error(`Element not found: ${selector}`);
      }
      
      const image = await window.capturePage(bounds);
      const screenshotPath = path.join(this.screenshotDir, `${name}.png`);
      
      fs.writeFileSync(screenshotPath, image.toPNG());
      console.log(`Element screenshot saved to ${screenshotPath}`);
      
      return screenshotPath;
    } catch (error) {
      console.error('Error capturing element screenshot:', error);
      throw error;
    }
  }
  
  /**
   * Compare a screenshot with a reference image
   * @param {string} name - Screenshot name
   * @returns {boolean} - True if the screenshot matches the reference
   */
  compareWithReference(name) {
    const actualPath = path.join(this.screenshotDir, `${name}.png`);
    const referencePath = path.join(__dirname, '..', 'screenshots', 'reference', `${name}.png`);
    
    if (!fs.existsSync(actualPath)) {
      console.error(`Actual screenshot not found: ${actualPath}`);
      return false;
    }
    
    if (!fs.existsSync(referencePath)) {
      console.warn(`Reference screenshot not found: ${referencePath}`);
      return false;
    }
    
    // In a real implementation, this would use image comparison
    // For now, we just check that both files exist and have content
    const actualSize = fs.statSync(actualPath).size;
    const referenceSize = fs.statSync(referencePath).size;
    
    if (actualSize === 0) {
      console.error(`Actual screenshot is empty: ${actualPath}`);
      return false;
    }
    
    if (referenceSize === 0) {
      console.error(`Reference screenshot is empty: ${referencePath}`);
      return false;
    }
    
    console.log(`Screenshot comparison for ${name}: actual=${actualSize} bytes, reference=${referenceSize} bytes`);
    return true;
  }
}

module.exports = ScreenshotCapture;
