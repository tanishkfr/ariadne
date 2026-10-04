/**
 * Beacon entry point. Emits the document; the build writes it to dist/.
 */

import { documentBody } from "./app/shell.ts";

export function render(): string {
  return documentBody();
}