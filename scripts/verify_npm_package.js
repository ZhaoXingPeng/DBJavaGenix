"use strict";

const assert = require("node:assert/strict");
const { execFileSync, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const PACKAGE_NAME = "dbjavagenix-mcp-server";
const REQUIRED_PATHS = [
  "index.js",
  "package.json",
  "pyproject.toml",
  "requirements.txt",
  "README.md",
  "LICENSE",
  "src/dbjavagenix/cli.py",
  "src/dbjavagenix/config/default_type_mapping.yaml",
  "src/dbjavagenix/templates/java/sb35-java21/entity.mustache",
];
const FORBIDDEN_PREFIXES = [
  ".claude/",
  ".github/",
  ".idea/",
  ".vscode/",
  "docs/",
  "htmlcov/",
  "iteration-plan/",
  "src/dbjavagenix.egg-info/",
  "tests/",
];
const FORBIDDEN_SUFFIXES = [".pyc"];

function npmCommand() {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

function runNpm(args, cwd = ROOT) {
  try {
    return execFileSync(npmCommand(), args, {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      shell: process.platform === "win32",
    });
  } catch (error) {
    const stdout = error.stdout ? error.stdout.toString() : "";
    const stderr = error.stderr ? error.stderr.toString() : "";
    throw new Error(`npm ${args.join(" ")} failed:\n${stdout}${stderr}`, { cause: error });
  }
}

function readManifest(args) {
  const output = runNpm(args);
  const manifest = JSON.parse(output);
  assert.equal(manifest.length, 1, "npm pack must return exactly one manifest entry");
  return manifest[0];
}

function assertManifest(manifest) {
  const paths = new Set(manifest.files.map((file) => file.path));
  const missing = REQUIRED_PATHS.filter((file) => !paths.has(file));
  assert.deepEqual(missing, [], `npm package is missing runtime files: ${missing.join(", ")}`);

  const forbidden = [...paths].filter((file) =>
    FORBIDDEN_PREFIXES.some((prefix) => file.startsWith(prefix)) ||
    FORBIDDEN_SUFFIXES.some((suffix) => file.endsWith(suffix)),
  );
  assert.deepEqual(forbidden, [], `npm package contains forbidden files: ${forbidden.join(", ")}`);
}

function replaceInstalledBackend(packageRoot, markerPath) {
  const backendRoot = path.join(packageRoot, "src", "dbjavagenix");
  fs.writeFileSync(path.join(backendRoot, "__init__.py"), "# package smoke backend\n", "utf8");
  fs.writeFileSync(
    path.join(backendRoot, "cli.py"),
    [
      "import os",
      "import sys",
      "from pathlib import Path",
      "",
      'Path(os.environ["DBJAVAGENIX_PACKAGE_SMOKE_MARKER"]).write_text("started\\n", encoding="utf-8")',
      'print("package smoke backend started", file=sys.stderr)',
      "",
    ].join("\n"),
    "utf8",
  );
}

function verifyInstalledWrapper(archivePath, temporaryRoot) {
  const installRoot = path.join(temporaryRoot, "installed");
  runNpm(["install", "--ignore-scripts", "--no-audit", "--no-fund", "--prefix", installRoot, archivePath]);

  const packageRoot = path.join(installRoot, "node_modules", PACKAGE_NAME);
  const entryPoint = path.join(packageRoot, "index.js");
  assert.ok(fs.existsSync(path.join(packageRoot, "src", "dbjavagenix", "cli.py")));

  const backendMarker = path.join(temporaryRoot, "package-smoke-backend.txt");
  replaceInstalledBackend(packageRoot, backendMarker);
  const result = spawnSync(process.execPath, [entryPoint], {
    cwd: packageRoot,
    encoding: "utf8",
    env: {
      ...process.env,
      DBJAVAGENIX_PACKAGE_SMOKE_MARKER: backendMarker,
    },
  });

  assert.equal(result.status, 0, `installed wrapper failed: ${result.stderr}`);
  assert.ok(fs.existsSync(backendMarker), "wrapper did not run the installed Python backend");
  assert.equal(result.stdout, "", "wrapper must reserve stdout for MCP JSON-RPC");
  assert.match(result.stderr, /Starting Python backend in stdio mode/);
  assert.match(result.stderr, /package smoke backend started/);
}

function main() {
  const dryRunManifest = readManifest(["pack", "--dry-run", "--json"]);
  assertManifest(dryRunManifest);

  const temporaryRoot = fs.mkdtempSync(path.join(os.tmpdir(), "dbjavagenix-npm-package-"));
  try {
    const packedManifest = readManifest([
      "pack",
      "--json",
      "--pack-destination",
      temporaryRoot,
    ]);
    assertManifest(packedManifest);
    const archivePath = path.join(temporaryRoot, packedManifest.filename);
    assert.ok(fs.existsSync(archivePath), `npm archive was not created: ${archivePath}`);
    verifyInstalledWrapper(archivePath, temporaryRoot);
    console.log(
      `NPM package contract valid: ${dryRunManifest.entryCount} files, ` +
        `${dryRunManifest.unpackedSize} unpacked bytes`,
    );
  } finally {
    fs.rmSync(temporaryRoot, { recursive: true, force: true });
  }
}

main();
