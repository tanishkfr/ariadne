# 24 — Platform Design Profiles

```text
Design Specificity Grammar   what is true of any product on any surface
        +
Platform Profile            what is additionally true of one surface
```

## Why the separation is structural

Every design system eventually absorbs the vocabulary of whatever platform somebody last
built for, and then quietly generalises it. SF Symbols becomes a design decision. 44pt
becomes a spacing rule. A safe-area inset becomes a layout principle. Each hop is
individually reasonable and collectively the grammar stops describing design and starts
describing one platform.

So the two are separate records, and **the grammar may only cite the universal one**.

A platform rule that happens to be justified on its own platform is *not* promoted by being
true. iPhone viewport dimensions are true of iPhone and false of a 27-inch display, and that
is not a matter of degree.

## Universal rules

```text
hierarchy before decoration
content before layout
meaning before aesthetic adjective
roles before literal values
divergence before convergence
a direction knows its own failure mode
project identity outranks external inspiration
render before judging
critique arrives without the implementer's rationale
```

Deliberately abstract: none of these is expressible as a number, which is why none of them can
leak a platform detail.

## Platform profiles

`web` · `desktop` · `ios` · `android` · `spatial`

`web` and `desktop` are universal-*ish* rather than universal: a desktop app has window
chrome and a menu bar that a web page does not. `spatial` exists so a future headset build has
somewhere honest to put its rules rather than smuggling them into `web`.

`profile_for()` **raises** on an unknown platform. Returning an empty profile would be worse:
the caller would proceed with no constraints and record that it had constraints.

Selected platform rules:

```text
ios       safe-area insets · 44pt minimum control target · SF Symbols · SwiftUI primitives ·
          Liquid Glass · UIScrollView keyboard avoidance · iPhone/iPad viewport dimensions ·
          lifecycle and background-state transitions
android   Material 3 elevation and dynamic colour · 48dp minimum target · adaptive window
          size classes · predictive back · cutout and gesture-bar insets
desktop   window chrome, menu bar, native dialogs · keyboard accelerators · pointer-device
          target sizing · multi-window and multi-monitor ownership
web       viewport units and the document scroll container · browser chrome changing
          available height · focus-visible heuristics
spatial   volume-relative control sizing · reach and comfort envelopes · stereo and
          focal-plane typography · hands, gaze and voice as simultaneous input
```

None of these is banned. They are what a profile is *for*.

## The leak check

`platform_rule_leaks()` returns the offending phrases rather than a boolean, because a caller
needs to say **which** rule leaked. Matching is over distinctive tokens rather than full
strings: the same rule arrives in a dozen phrasings, and a rule that can only be caught in its
original wording is not a boundary.

```text
assert_no_leak("use a 44pt minimum interactive control target", label="direction")
  -> the direction cites platform-specific rules as universal design principles: ios: 44pt
     minimum interactive control target. Record it under a Platform Profile, or state the
     general principle the platform rule merely instantiates.
```

`bound_platform_profiles()` attaches platform rules to a record while keeping them out of the
universal body:

```python
unbound = bound_platform_profiles(["44pt minimum interactive control target"], platform="")
assert unbound["platform_bound"]      # an iOS rule with no platform named is pretending to be universal
assert not unbound["platform_rules"]  # and there are no profile rules to bind it to

bound = bound_platform_profiles(["44pt minimum interactive control target"], platform="ios")
assert bound["platform_profile"] == "ios"
assert not bound["platform_bound"]    # a named profile is where the rule legitimately lives
```

That last case is the point of the whole split: **the same sentence is a defect or a fact
depending on whether a platform is named.**

## Tests

```text
platform-specific rule does not leak into universal grammar
a universal record citing an ios rule is refused
an unknown platform profile raises rather than returning empty
platform rules are bound to the profile, not the universal body
```

and the mutation that keeps them honest:

```text
M33  a platform-specific rule leaks into the universal grammar
```

## See also

- [21 — Design Specificity Grammar](21-DESIGN-SPECIFICITY-GRAMMAR.md)
- [28 — AR-222D Results](28-AR-222D-RESULTS.md)
