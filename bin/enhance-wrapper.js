#!/usr/bin/env node

const { spawn } = require('child_process');

const args = process.argv.slice(2);
const command = 'enhance';

const child = spawn(command, args, { stdio: 'inherit' });

child.on('error', (err) => {
  if (err.code === 'ENOENT') {
    console.error('Error: `enhance` command not found.');
    console.error('Please ensure Python is installed and `enhance` is in your PATH.');
    console.error('You may need to run `pip install enhance-this --upgrade`.');
  } else {
    console.error(`Error executing command: ${err.message}`);
  }
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code);
});
