/**
 * Feature: cumulative miniprogram release test runner.
 * Responsibilities: discover and execute every *.test.js file in a stable order.
 * Does not own: individual feature assertions or production behavior.
 * Plan task: DEV-18.
 */

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const testDir = __dirname;
const runnerName = path.basename(__filename);
const testFiles = fs
  .readdirSync(testDir)
  .filter((name) => name.endsWith(".test.js") && name !== runnerName)
  .sort();

let passed = 0;
for (const testFile of testFiles) {
  const fullPath = path.join(testDir, testFile);
  const result = spawnSync(process.execPath, [fullPath], { stdio: "inherit" });
  if (result.status !== 0) {
    console.error(`FAILED: ${testFile}`);
    process.exit(result.status || 1);
  }
  passed += 1;
}

console.log(`miniprogram cumulative tests: ${passed}/${testFiles.length} PASS`);
