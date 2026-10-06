# Two-pane split with a keyboard-operable divider

Recorded implementation pattern. Ariadne project note, Apache-2.0 (this
repository).

## Problem

A resizable side panel is usually implemented with a mouse-only drag handle. That
excludes keyboard users entirely, and it is also fiddly for pointer users on a
trackpad, because a four-pixel target has to be hit precisely.

## Contract

1. The divider is a `separator` with `aria-orientation` set to the axis it resizes.
2. The divider is focusable (`tabindex="0"`) and carries an accessible name.
3. Arrow keys move the divider by a fixed step along the axis.
4. `Home` and `End` move it to its minimum and maximum.
5. Both bounds are enforced on every path, so no sequence of key presses can produce
   an unusable pane.
6. Collapsing preserves the size the user last chose, so re-expanding restores it.
7. The current size is exposed as `aria-valuenow` while the pane is uncollapsed.

## Non-goals

This note describes an interaction contract only. It says nothing about colour, type,
spacing, radius or any other visual language, and using it grants no permission to
adopt the source's appearance.

## How Ariadne uses it

The contract is adapted onto the project's own `panel()` primitive and its own
`density` helpers. No source from any source is copied, and the implementation
reference is recorded with its licence, revision, files inspected and reuse status
so a reader can tell which of those happened.