#!/usr/bin/env node
/**
 * DBJavaGenix MCP Server Entry Point
 * 作者: ZXP (2638265504@qq.com)
 * 用于Cherry Studio等MCP客户端的标准化入口
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const projectDir = __dirname;
const srcDir = path.join(projectDir, 'src');

console.log('DBJavaGenix MCP Server v0.1.0');
console.log('🚀 Starting server in stdio mode...');
console.log(`📁 Project: ${projectDir}`);
console.log(`📂 Source: ${srcDir}`);

// 验证项目结构
if (!fs.existsSync(srcDir)) {
  console.error('❌ Error: Source directory not found');
  console.error(`Expected: ${srcDir}`);
  process.exit(1);
}

if (!fs.existsSync(path.join(srcDir, 'dbjavagenix'))) {
  console.error('❌ Error: dbjavagenix module not found');
  console.error(`Expected: ${path.join(srcDir, 'dbjavagenix')}`);
  process.exit(1);
}

// 启动Python MCP服务器
const python = spawn('python', ['-m', 'dbjavagenix.cli', 'server'], {
  cwd: projectDir,
  env: {
    ...process.env,
    PYTHONPATH: srcDir
  },
  stdio: 'inherit'
});

python.on('error', (err) => {
  console.error('❌ Failed to start Python MCP server:', err.message);
  console.error('💡 Make sure Python is installed and available in PATH');
  console.error('💡 Make sure dbjavagenix module is properly installed');
  process.exit(1);
});

python.on('close', (code) => {
  if (code !== 0) {
    console.error(`❌ Python process exited with code ${code}`);
  }
  process.exit(code);
});

// 优雅关闭处理
process.on('SIGINT', () => {
  console.log('\n🛑 Received SIGINT, shutting down...');
  python.kill('SIGINT');
});

process.on('SIGTERM', () => {
  console.log('\n🛑 Received SIGTERM, shutting down...');
  python.kill('SIGTERM');
});

process.on('uncaughtException', (err) => {
  console.error('❌ Uncaught exception:', err);
  python.kill('SIGTERM');
  process.exit(1);
});