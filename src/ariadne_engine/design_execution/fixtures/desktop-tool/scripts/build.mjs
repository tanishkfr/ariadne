#!/usr/bin/env node
/**
 * Beacon's build. Zero dependencies, offline, deterministic.
 *
 * Emits dist/index.html and dist/styles/. A build that needs a package manager to
 * run is a build that cannot be used to prove anything offline, so this one has no
 * dependencies at all - not even the TypeScript compiler, which typecheck runs
 * separately.
 */

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");

const STYLESHEETS = ["styles/tokens.css", "styles/app.css"];

function requireBalanced(text, label) {
  const opens = (text.match(/\{/g) ?? []).length;
  const closes = (text.match(/\}/g) ?? []).length;
  if (opens !== closes) {
    throw new Error(`${label}: ${opens} opening braces against ${closes} closing braces`);
  }
  return text;
}

async function bundleShell() {
  const { render } = await import(pathToFileURL(join(root, "src", "index.ts")).href);
  return render();
}

async function main() {
  await mkdir(join(dist, "styles"), { recursive: true });

  for (const relative of STYLESHEETS) {
    const source = await readFile(join(root, "src", relative), "utf8");
    requireBalanced(source, relative);
    await writeFile(join(dist, relative), source, "utf8");
  }

  const html = await bundleShell();
  requireBalanced(html, "rendered shell");

  for (const landmark of ["<main", "<nav", "<section"]) {
    if (!html.includes(landmark)) {
      throw new Error(`the built shell is missing the ${landmark}> landmark`);
    }
  }

  await writeFile(join(dist, "index.html"), html, "utf8");
  const bytes = Buffer.byteLength(html, "utf8");
  process.stdout.write(`beacon build ok: dist/index.html (${bytes} bytes, ${STYLESHEETS.length} stylesheets)\n`);
}

main().catch((error) => {
  process.stderr.write(`beacon build failed: ${error.message}\n`);
  process.exitCode = 1;
});