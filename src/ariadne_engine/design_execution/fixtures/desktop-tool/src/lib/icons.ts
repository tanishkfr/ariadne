/**
 * Beacon's icon set.
 *
 * Inline SVG paths, drawn for this project. No third-party icon library is
 * vendored and no reference product's iconography is copied in.
 */

import type { IconName } from "./ui.ts";

const PATHS: Record<IconName, string> = {
  request: "M3 5h14M3 10h14M3 15h9",
  history: "M4 8a6 6 0 1 1 1 5M4 8V4M4 8h4",
  logs: "M3 4h14M3 8h14M3 12h14M3 16h8",
  settings: "M10 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM10 2v3M10 15v3M2 10h3M15 10h3",
  search: "M9 3a6 6 0 1 0 0 12A6 6 0 0 0 9 3zM13.5 13.5 18 18",
  play: "M6 4l10 6-10 6z",
  collapse: "M12 4v12M6 10l6 6 6-6",
};

export function icon(name: IconName, accessibleName = ""): string {
  const path = PATHS[name];
  if (!path) {
    throw new Error(`unknown icon: ${name}`);
  }
  const label = accessibleName
    ? ` role="img" aria-label="${accessibleName}"`
    : ' aria-hidden="true"';
  return `<svg class="icon icon--${name}" viewBox="0 0 20 20"${label}><path d="${path}"/></svg>`;
}

/** An icon-only control still needs a name, or it is unusable with a screen reader. */
export function iconButton(name: IconName, accessibleName: string, target: string): string {
  return `<button type="button" class="icon-btn" aria-label="${accessibleName}" data-target="${target}">`
    + `${icon(name, accessibleName)}</button>`;
}