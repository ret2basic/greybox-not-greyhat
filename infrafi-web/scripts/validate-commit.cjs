#!/usr/bin/env node

const fs = require('fs');

// Read the commit message from the file
const commitMsgFile = process.argv[2];
const commitMsg = fs.readFileSync(commitMsgFile, 'utf8').trim();

// Check if the commit message follows the [DAWN-xxx] format
// Allow multi-line commit messages after the first line
const dawnPattern = /^\[DAWN-\d+\]\s+(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?:\s.+/;

if (!dawnPattern.test(commitMsg)) {
  console.error('❌ Invalid commit message format!');
  console.error('');
  console.error('Your commit message must follow this format:');
  console.error('[DAWN-xxx] type: commit message');
  console.error('');
  console.error('Where:');
  console.error('- DAWN-xxx is your Linear ticket number');
  console.error('- type is one of: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert');
  console.error('- commit message describes what you changed');
  console.error('');
  console.error('Examples:');
  console.error('[DAWN-123] feat: add user authentication');
  console.error('[DAWN-456] fix: resolve login redirect issue');
  console.error('[DAWN-789] docs: update API documentation');
  console.error('');
  console.error('Multi-line messages are also supported:');
  console.error('[DAWN-123] feat: add user authentication');
  console.error('');
  console.error('This feature includes login, registration, and password');
  console.error('reset functionality with proper validation.');
  console.error('');
  console.error('Your commit message:');
  console.error(`"${commitMsg}"`);
  process.exit(1);
}

console.log('✅ Commit message format is valid!');
process.exit(0);
