/**
 * The Beacon shell.
 *
 * Pre-implementation state: a centred welcome panel over a glassy card grid, with
 * every action shaped like a pill. It renders and it works, and it is the generic
 * version of itself.
 */

import { DENSITY } from "../lib/density.ts";
import { button, divider, logRow, logTable, panel } from "../lib/ui.ts";
import { ROUTES, defaultRoute } from "./routes.ts";

const SAMPLE_ROWS: readonly [string, number, string, string][] = [
  ["10:02:11.418", 200, "GET", "/v1/sessions"],
  ["10:02:11.902", 200, "POST", "/v1/sessions/8f2c/events"],
  ["10:02:12.140", 404, "GET", "/v1/sessions/8f2c/tags"],
  ["10:02:12.771", 500, "POST", "/v1/sessions/8f2c/events"],
  ["10:02:13.055", 200, "DELETE", "/v1/sessions/8f2c"],
];

function welcomePanel(): string {
  return panel(
    { id: "welcome", title: "Beacon", surface: "raised", scrollable: false },
    [
      '  <div class="hero">',
      '    <h1 class="cta-label">Ship requests faster</h1>',
      '    <p>Everything you need to inspect, replay and audit API traffic.</p>',
      '    <div class="chip-row">',
      `      ${button("New request", "primary")}`,
      `      ${button("Open history")}`,
      "    </div>",
      "  </div>",
      '  <div class="card-grid">',
      `    ${panel({ id: "quickstart", title: "Quickstart", surface: "raised", scrollable: false }, '<p>Send your first request in three steps.</p>')}`,
      `    ${panel({ id: "environments", title: "Environments", surface: "raised", scrollable: false }, '<p>Three environments configured.</p>')}`,
      `    ${panel({ id: "recent", title: "Recent", surface: "raised", scrollable: false }, '<p>Twelve requests in the last hour.</p>')}`,
      "  </div>",
    ].join("\n")
  );
}

function logPanel(): string {
  const rows = SAMPLE_ROWS.map(([time, status, method, path]) => logRow(time, status, method, path));
  return panel(
    { id: "log", title: "Recent responses", surface: "surface", scrollable: true },
    logTable(rows)
  );
}

export function shell(activeRoute = defaultRoute().id): string {
  const primary = ROUTES.filter((entry) => entry.group === "primary");
  const railItems = primary
    .map((entry) => `<a class="chip" href="#${entry.id}" data-active="${entry.id === activeRoute}">${entry.label}</a>`)
    .join("\n  ");
  return [
    `<main class="app" data-row-height="${DENSITY.rowHeight}">`,
    `  <nav class="chip-row" aria-label="Sections">`,
    `  ${railItems}`,
    "  </nav>",
    divider(),
    `  ${welcomePanel()}`,
    `  ${logPanel()}`,
    "</main>",
  ].join("\n");
}

export function documentBody(): string {
  return [
    "<!doctype html>",
    '<html lang="en">',
    "<head>",
    '  <meta charset="utf-8">',
    '  <meta name="viewport" content="width=device-width, initial-scale=1">',
    "  <title>Beacon</title>",
    '  <link rel="stylesheet" href="styles/tokens.css">',
    '  <link rel="stylesheet" href="styles/app.css">',
    "</head>",
    "<body>",
    shell(),
    "</body>",
    "</html>",
  ].join("\n");
}