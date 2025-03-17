/**
 * Test runner script for Cobalt macOS app
 * This script runs tests and generates proper test reports
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Configuration
const TEST_DIRS = ['unit', 'integration', 'e2e'];
const REPORT_TEMPLATE = path.join(__dirname, 'TEST_REPORT_TEMPLATE.md');
const REPORT_OUTPUT = path.join(__dirname, 'TEST_REPORT.md');

// Create test report template if it doesn't exist
if (!fs.existsSync(REPORT_TEMPLATE)) {
  console.log('Creating test report template...');
  const template = `# Test Report

## Overview

This report contains the results of automated tests for the Cobalt macOS application.

## Test Environment

- **OS**: ${process.platform} ${process.version}
- **Node Version**: ${process.version}
- **Test Date**: ${new Date().toISOString()}

## Test Results

### Unit Tests

| Test Suite | Status | Details |
|------------|--------|---------|
| Utils | ⏳ Not Run | |

### Integration Tests

| Test Suite | Status | Details |
|------------|--------|---------|
| Video Download | ⏳ Not Run | |

## Running Tests

To run the tests:

\`\`\`bash
# Run all tests
npm test

# Run unit tests only
npm run test:unit

# Run integration tests only
npm run test:integration
\`\`\`

## Notes

This test report template will be automatically updated with actual test results when tests are run.
`;
  fs.writeFileSync(REPORT_TEMPLATE, template);
}

// Ensure directories exist
TEST_DIRS.forEach(dir => {
  const fullPath = path.join(__dirname, dir);
  if (!fs.existsSync(fullPath)) {
    console.log(`Creating ${dir} test directory...`);
    fs.mkdirSync(fullPath, { recursive: true });
  }
});

// Ensure screenshots directory exists
const screenshotsDir = path.join(__dirname, 'screenshots', 'actual');
if (!fs.existsSync(screenshotsDir)) {
  console.log('Creating screenshots directory...');
  fs.mkdirSync(screenshotsDir, { recursive: true });
}

// Run tests
console.log('Running tests...');

const results = {};

// Run unit tests
try {
  console.log('Running unit tests...');
  const unitOutput = execSync('npm run test:unit', { encoding: 'utf8' });
  console.log(unitOutput);
  results.unit = { status: 'Passed', details: 'All tests passed' };
} catch (error) {
  console.error('Unit tests failed:', error.message);
  results.unit = { status: 'Failed', details: error.message };
}

// Run integration tests
try {
  console.log('Running integration tests...');
  const integrationOutput = execSync('npm run test:integration', { encoding: 'utf8' });
  console.log(integrationOutput);
  results.integration = { status: 'Passed', details: 'All tests passed' };
} catch (error) {
  console.error('Integration tests failed:', error.message);
  results.integration = { status: 'Failed', details: error.message };
}

// Generate test report
console.log('Generating test report...');

let reportTemplate = fs.readFileSync(REPORT_TEMPLATE, 'utf8');

// Update unit test results
if (results.unit) {
  const status = results.unit.status === 'Passed' ? '✅ Passed' : '❌ Failed';
  reportTemplate = reportTemplate.replace(
    /\| Utils \| ⏳ Not Run \| \|/,
    `| Utils | ${status} | ${results.unit.details} |`
  );
}

// Update integration test results
if (results.integration) {
  const status = results.integration.status === 'Passed' ? '✅ Passed' : '❌ Failed';
  reportTemplate = reportTemplate.replace(
    /\| Video Download \| ⏳ Not Run \| \|/,
    `| Video Download | ${status} | ${results.integration.details} |`
  );
}

// Update test date
reportTemplate = reportTemplate.replace(
  /\*\*Test Date\*\*: .*/,
  `**Test Date**: ${new Date().toISOString()}`
);

// Write updated report
fs.writeFileSync(REPORT_OUTPUT, reportTemplate);

console.log(`Test report generated at ${REPORT_OUTPUT}`);
