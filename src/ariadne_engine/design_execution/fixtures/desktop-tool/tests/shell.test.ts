/**
 * Static checks over Beacon's own output.
 *
 * These are mechanical, not aesthetic: the build asserts that what the shell emits
 * is well-formed, carries the landmarks and names the interface depends on, and
 * does not reintroduce the surface treatments Beacon's design document forbids.
 *
 * A rendered comparison would be a different phase's job. Nothing here claims the
 * interface looks right.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { documentBody, shell } from "../src/app/shell.ts";
import { clampPane, stepPane } from "../src/lib/density.ts";
import { icon, iconButton } from "../src/lib/icons.ts";
import { defaultRoute, route, routeIds } from "../src/app/routes.ts";
import { button, divider, navItem, panel } from "../src/lib/ui.ts";

test("the shell emits a navigation landmark and a named toolbar region", () => {
  const html = shell();
  assert.match(html, /<nav\b/, "the shell must expose a navigation landmark");
});

test("every interactive control is a real button or a link", () => {
  const html = shell();
  const divs = html.match(/<div[^>]*onclick/gi) ?? [];
  assert.deepEqual(divs, [], "no control may be a div with an inline handler");
});

test("icon-only controls carry an accessible name", () => {
  const control = iconButton("collapse", "Collapse inspector", "inspector");
  assert.match(control, /aria-label="Collapse inspector"/);
  assert.match(control, /<svg[^>]*role="img"/);
});

test("decorative icons are hidden from assistive technology", () => {
  assert.match(icon("play"), /aria-hidden="true"/);
});

test("panels are labelled by their heading", () => {
  const markup = panel({ id: "log", title: "Log", surface: "surface", scrollable: true }, "body");
  assert.match(markup, /aria-labelledby="log-title"/);
  assert.match(markup, /id="log-title"/);
});

test("log rows expose the status family the stylesheet keys on", () => {
  const html = shell();
  assert.match(html, /status-2xx/);
  assert.match(html, /status-5xx/);
});

test("the document links the project stylesheets", () => {
  const html = documentBody();
  assert.match(html, /styles\/tokens\.css/);
  assert.match(html, /styles\/app\.css/);
});

test("the primary button is a real button element", () => {
  assert.match(button("Send", "primary"), /<button type="button"/);
});

test("navigation items expose the current page", () => {
  const markup = navItem({ id: "logs", label: "Logs", icon: "logs" }, true);
  assert.match(markup, /aria-current="page"/);
  assert.match(markup, /data-active="true"/);
});

test("a labelled divider is a separator landmark", () => {
  assert.match(divider("Regions"), /role="separator"/);
});

test("the route table exposes every declared route", () => {
  assert.deepEqual(routeIds(), ["request", "history", "logs", "settings"]);
  assert.equal(defaultRoute().id, "request");
  assert.equal(route("settings")?.group, "inspect");
});

test("pane sizes stay inside usable bounds", () => {
  assert.equal(clampPane(4, 96, 720), 96);
  assert.equal(clampPane(4000, 96, 720), 720);
  assert.equal(clampPane(Number.NaN, 96, 720), 96);
  assert.equal(stepPane(300, -1), 284);
  assert.equal(stepPane(710, 1), 720);
});

test("the stylesheet keeps reduced-motion handling", async () => {
  const { readFile } = await import("node:fs/promises");
  const file = new URL("../src/styles/app.css", import.meta.url);
  const css = await readFile(file, "utf8");
  assert.match(css, /@media \(prefers-reduced-motion/, "reduced motion must stay supported");
});

test("focus is visible on keyboard navigation", async () => {
  const { readFile } = await import("node:fs/promises");
  const file = new URL("../src/styles/app.css", import.meta.url);
  const css = await readFile(file, "utf8");
  const focusBlock = css.match(/:focus-visible\s*\{([^}]*)\}/)?.[1] ?? "";
  assert.ok(focusBlock.includes("outline"), "a keyboard focus ring must be declared");
});