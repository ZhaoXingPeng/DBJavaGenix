#!/usr/bin/env node
/**
 * DBJavaGenix MCP Server entry point
 *
 * MCP 协议走 stdio: 客户端把 JSON-RPC 写到子进程 stdin, 从 stdout 读响应。
 * 任何 wrapper 启动信息必须写到 **stderr**, 否则会污染 stdout 上的 JSON-RPC 流,
 * 客户端 (Cherry Studio / Claude Desktop / Cursor 等) 会解析失败。
 */

'use strict';

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const projectDir = __dirname;
const srcDir = path.join(projectDir, 'src');

// 用 stderr 输出启动信息, stdout 留给 MCP JSON-RPC.
const log = (...args) => process.stderr.write(args.join(' ') + '\n');

log('DBJavaGenix MCP Server v0.1.0');
log('Starting Python backend in stdio mode...');

if (!fs.existsSync(srcDir) || !fs.existsSync(path.join(srcDir, 'dbjavagenix'))) {
  log('ERROR: dbjavagenix source not found at', srcDir);
  log('  Did you `pip install -e .` or run from a checkout?');
  process.exit(1);
}

const py = spawn('python', ['-m', 'dbjavagenix.cli', 'server'], {
  cwd: projectDir,
  env: { ...process.env, PYTHONPATH: srcDir },
  stdio: 'inherit',
});

py.on('error', (err) => {
  log('ERROR: failed to spawn python:', err.message);
  log('  Make sure python is on PATH and dbjavagenix module is installed.');
  process.exit(1);
});

py.on('close', (code) => {
  if (code !== 0) log(`Python process exited with code ${code}`);
  process.exit(code === null ? 1 : code);
});

const forward = (sig) => () => {
  log(`Received ${sig}, forwarding to backend...`);
  py.kill(sig);
};
process.on('SIGINT', forward('SIGINT'));
process.on('SIGTERM', forward('SIGTERM'));

process.on('uncaughtException', (err) => {
  log('Uncaught exception:', err && err.stack ? err.stack : err);
  py.kill('SIGTERM');
  process.exit(1);
});
