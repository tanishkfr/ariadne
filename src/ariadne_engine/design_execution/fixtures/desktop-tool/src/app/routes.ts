/**
 * Beacon's route table.
 *
 * Navigation structure is a material design decision. This table is what makes it
 * explicit rather than implied by the markup.
 */

import type { IconName } from "../lib/ui.ts";

export interface Route {
  readonly id: string;
  readonly label: string;
  readonly icon: IconName;
  readonly group: "primary" | "inspect";
}

export const ROUTES: readonly Route[] = [
  { id: "request", label: "Request", icon: "request", group: "primary" },
  { id: "history", label: "History", icon: "history", group: "primary" },
  { id: "logs", label: "Logs", icon: "logs", group: "primary" },
  { id: "settings", label: "Settings", icon: "settings", group: "inspect" },
] as const;

export function route(id: string): Route | undefined {
  return ROUTES.find((entry) => entry.id === id);
}

export function routeIds(): string[] {
  return ROUTES.map((entry) => entry.id);
}

/** The first primary route, used as the shell's default view. */
export function defaultRoute(): Route {
  const first = ROUTES[0];
  if (!first) {
    throw new Error("Beacon declares no routes");
  }
  return first;
}