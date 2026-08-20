# UI LIBRARIES

**All research-only by default.** Read them, take the technique, build your own.

Policy: [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 4. Method: [component-research](../skills/component-research.md).

---

## Why research-only

These catalogues are genuinely good, and that is the problem. Three specific risks:

1. **They carry a recognisable house style.** Using them makes your work look like everyone else using them — and a lot of people are using them. Recognisability is the opposite of the goal.
2. **Most are copy-paste catalogues by design.** Taking the technique *is* the intended use. There is often nothing to install.
3. **A component you wrote can be art-directed. A component you installed resists it** — it has its own tokens, its own assumptions, usually its own Tailwind setup.

**Approved use:** open it, understand the technique, close it, implement your version against your tokens. Record what you learned in `RESEARCH.md` with the source URL.

**To actually install one:** full G2 with a statement of why building it yourself is the wrong call ([LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 6).

---

## The set

**Status note:** these are the sources you collected. **I have not visited or evaluated any of them in this session** — no claim below about maintenance, licensing, or quality has been verified. Check freshness before relying on any of them ([RESEARCH-POLICY.md](../RESEARCH-POLICY.md)).

| Source | Reported for | Watch for |
|---|---|---|
| [ui.watermelon.sh](https://ui.watermelon.sh/) | Components | |
| [motion-primitives.com](https://motion-primitives.com/) | Motion components | Overlaps Motion.dev — take the technique, not the layer |
| [kokonutui.com](https://kokonutui.com/) | Components | |
| [bklit.ui](https://bklit.ui/) | Components | URL may need verifying |
| [reactbits.dev](https://reactbits.dev/) | Effects and interactions | Copy-paste by design |
| [8bitcn.com](https://8bitcn.com/) | Retro/pixel styling | Genuinely useful for [game-experiment](../modes/game-experiment.md) — but "retro" still needs a thesis |
| [magicui.design](https://magicui.design/) | Animated components | Strong house style; highly recognisable |
| [ui.aceternity.com](https://ui.aceternity.com/) | Animated components | The most recognisable of the set. Using it as-is is instantly identifiable. |

**Before taking anything from any of these:**

- Keyboard-test the actual demo. Many showcase components are mouse-only and unfixable without a rewrite.
- Check what it animates. Compositor-only (`transform`, `opacity`), or `width`/`filter`/`box-shadow`?
- Check the Tailwind assumption. Most assume it; if your project does not use it, the technique still transfers but the code does not.

---

## The one exception: unstyled primitives

**Radix UI** (`@radix-ui/*`) is Conditional rather than research-only ([LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 3), because it is unstyled. It solves focus management, ARIA, and collision detection — correctness problems that are genuinely hard and have real accessibility consequences when done badly — without imposing any visual identity.

**The dividing line: install for correctness, build for expression.**

A dialog's focus trap is correctness. Use a library. A hover interaction that is part of your signature moment is expression. Build it, or it will look like everyone else's.

---

## Forbidden by default

**Styled component kits** — MUI, Chakra, Ant Design, Bootstrap, DaisyUI, and anything similar.

Not because they are bad. Because they impose a visual identity, and that makes portfolio-quality art direction effectively impossible. This is criterion 1 in [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 5, and it is the criterion that matters most for what you are trying to build.

Using one is the difference between art direction and template assembly.

---

## The real risk

**Component-library soup**: five libraries, five visual languages, none of them yours. It is on the anti-generic list ([DESIGN-TASTE.md](../DESIGN-TASTE.md) section 8) and it happens gradually, one reasonable-seeming install at a time.

The countermeasure is structural: one token system, and G2 on every package. Not discipline — a gate.
