/**
 * Density helpers.
 *
 * A tool used all day needs a row height and a gutter it can commit to, rather than
 * one recomputed per component.
 */

export const DENSITY = {
  rowHeight: 24,
  navRailWidth: 176,
  inspectorWidth: 320,
  gutter: 8,
} as const;

export type DensityKey = keyof typeof DENSITY;

export function density(key: DensityKey): number {
  const value = DENSITY[key];
  if (typeof value !== "number") {
    throw new Error(`unknown density token: ${key}`);
  }
  return value;
}

/** Clamp a size so a resized pane never becomes unusable. */
export function clampPane(size: number, min: number, max: number): number {
  if (!Number.isFinite(size)) {
    return min;
  }
  return Math.min(max, Math.max(min, Math.round(size)));
}

/** Step a pane size by a keyboard increment, clamped to its bounds. */
export function stepPane(size: number, direction: 1 | -1, step = 16): number {
  return clampPane(size + direction * step, 96, 720);
}