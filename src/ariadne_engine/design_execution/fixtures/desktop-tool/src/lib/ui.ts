/**
 * Beacon's existing interface primitives.
 *
 * This module predates the design work and is not part of it. It exists so that the
 * grounded implementation has real components to reuse, and so that "reuse what the
 * project already has" is testable rather than aspirational.
 */

export type SurfaceLevel = "canvas" | "surface" | "raised";

export type IconName =
  | "request"
  | "history"
  | "logs"
  | "settings"
  | "search"
  | "play"
  | "collapse";

export interface NavItemSpec {
  readonly id: string;
  readonly label: string;
  readonly icon: IconName;
}

export interface PanelSpec {
  readonly id: string;
  readonly title: string;
  readonly surface: SurfaceLevel;
  readonly scrollable: boolean;
}

/** A navigation entry in the rail. The rail owns focus order; items stay inert. */
export function navItem(spec: NavItemSpec, active: boolean): string {
  const state = active ? " data-active=\"true\"" : "";
  const pressed = active ? " aria-current=\"page\"" : "";
  return `<a class="nav-item" href="#${spec.id}" data-icon="${spec.icon}"${state}${pressed}>${spec.label}</a>`;
}

/** A titled panel on one of the three declared surface levels. */
export function panel(spec: PanelSpec, body: string): string {
  const scroll = spec.scrollable ? " data-scrollable=\"true\"" : "";
  return [
    `<section class="panel panel--${spec.surface}" id="${spec.id}" aria-labelledby="${spec.id}-title"${scroll}>`,
    `  <header class="panel__header"><h2 class="panel__title" id="${spec.id}-title">${spec.title}</h2></header>`,
    `  <div class="panel__body">${body}</div>`,
    "</section>",
  ].join("\n");
}

/** A compact action control. Real button semantics, always. */
export function button(label: string, variant: "default" | "primary" = "default"): string {
  const kind = variant === "primary" ? "btn btn--primary" : "btn";
  return `<button type="button" class="${kind}">${label}</button>`;
}

/** A toolbar holding grouped controls. */
export function toolbar(label: string, controls: readonly string[]): string {
  const body = controls.map((control) => `    ${control}`).join("\n");
  return [
    `<div class="toolbar" role="toolbar" aria-label="${label}">`,
    body,
    "</div>",
  ].join("\n");
}

/** A hairline rule separating two regions of the same surface. */
export function divider(label = ""): string {
  const role = label ? " role=\"separator\"" : "";
  return `<hr class="divider"${role}>`;
}

/** A table of log rows. Dense by construction; rows are already compact. */
export function logTable(rows: readonly string[]): string {
  const body = rows.map((row) => `      <tr>${row}</tr>`).join("\n");
  return [
    "<table class=\"log-table\">",
    "  <thead><tr><th scope=\"col\">time</th><th scope=\"col\">status</th><th scope=\"col\">method</th><th scope=\"col\">path</th></tr></thead>",
    "  <tbody>",
    body,
    "  </tbody>",
    "</table>",
  ].join("\n");
}

/** Row markup for one log entry, with the status class the stylesheet keys on. */
export function logRow(time: string, status: number, method: string, path: string): string {
  const family = Math.floor(status / 100);
  return `<td><code>${time}</code></td><td class="status-${family}xx"><code>${status}</code></td>`
    + `<td><code>${method}</code></td><td><code>${path}</code></td>`;
}

/** The surface a region sits on. Beacon declares exactly three. */
export function surfaceToken(level: SurfaceLevel): string {
  return `var(--${level})`;
}