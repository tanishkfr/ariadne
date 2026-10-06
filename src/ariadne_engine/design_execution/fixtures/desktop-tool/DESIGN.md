# Beacon — project design document

Beacon is a desktop developer tool. An engineer keeps it open beside an editor all
day: it sends HTTP requests, holds a large scrollback of responses, and shows
timestamps, status codes and payloads for thousands of log lines at a time.

This document is Beacon's own design intent. It is the authority for Beacon's
identity, and it outranks any external reference consulted while designing it.

## Identity

- The product is a working surface, not a landing page. There is no hero, no
  marketing headline, and no introductory copy.
- Beacon's accent colour is declared in `src/styles/tokens.css` as `--accent`. It is
  the product's own brand colour and is never taken from a reference.
- Beacon's typeface is the `--font-sans` stack in `src/styles/tokens.css`. It is not
  replaced by a reference's type family.

## Density

- Navigation, toolbars and tables are dense. Row heights stay small enough that a
  thousand log lines remain scannable without zooming out.
- Content and chrome are distinguished by surface level and a hairline rule, not by
  shadow, glow or rounded card edges.

## Surfaces

Exactly three surface levels exist: `canvas`, `surface` and `raised`. A fourth
surface level is a design decision that has to be justified, not a default.

## Motion

Motion is limited to state changes a user would otherwise have to hunt for:
selection, disclosure and panel resizing. Anything decorative is out of scope.
Reduced-motion is honoured: the `prefers-reduced-motion` media query is present in
`src/styles/app.css` and is not removed.

## Accessibility

- Every interactive element is a real focusable control with a visible focus ring.
- Navigation is a landmark. Icon-only controls carry an accessible name.
- Reduced-motion support is mandatory, not optional.

## Reuse

Beacon already ships its primitives in `src/lib/ui.ts` and `src/lib/icons.ts`.
New interface work extends them. A second implementation of an existing primitive is
a defect.