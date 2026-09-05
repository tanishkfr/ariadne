# SKILL: component-research

**Trigger** — a non-trivial interaction needs building and it is unclear how.
**Owner** — Researcher
**Inputs** — the interaction requirement from `DESIGN.md`, the project creative-evidence plan, and `references/capabilities.json` when this skill was selected
**Output** — a technique writeup in [`RESEARCH.md`](../templates/RESEARCH.md), and possibly a G2 dependency request

**The point of this skill is to take techniques, not dependencies.** Sources in [references/ui-libraries.md](../references/ui-libraries.md) are research-only by default ([LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 4).

**Evidence boundary** — a proposed resource needs an inspected source artifact,
the observed technique, an alternative, compatibility/licence evidence where
relevant, and an explicit build/install/skip decision. Recommendation is not
invocation; invocation is not completion; completion is not downstream use.

---

## Method

**1. State the interaction in behaviour, not implementation.** "A grid where hovering an item pushes neighbours aside with physical weight" — not "a magnetic hover grid". Behavioural descriptions are searchable and do not presuppose a solution.

**2. Ask whether it needs to exist.** Does the thesis require this interaction, or is it decoration? Decoration gets cut here, cheaply, rather than at S5 after it is built.

**3. Walk the minimum-solution ladder.** Existing project capability → native
platform primitive → smallest project-local implementation → already-approved
dependency → current registered capability → bounded external discovery. Stop
at the first sufficient rung. Do not research packages when an earlier rung
already solves the requirement.

When the registry supplies candidates, filter them by the project's behaviour,
accessibility, licence, maintenance, side effects, and visual direction. One
eligible candidate is still a proposal; competing candidates require a
project-specific comparison. A stale or unpinned row triggers research, not a
guess. A capability that conflicts with the approved visual language is
rejected even if it is popular.

**4. Find up to three implementations only when comparison remains necessary.**
From the registry, research sources, sites in the wild, or open source. For
each: what technique, what it costs, where it breaks. Record why rejected
candidates lost against this project rather than ranking by popularity.

**5. Extract the technique.** What is actually happening — a transform on a wrapper, an IntersectionObserver, a spring, a canvas layer, a CSS-only trick. Write the mechanism down in `RESEARCH.md` with the source URL. **You are done with the library at this point.**

**6. Decide: build or install.**

Build it yourself when — it is under ~150 lines; it needs to match your tokens; it is visible and judged; a library would impose its own visual identity.

Propose installing when — it solves genuinely hard correctness problems (focus management, ARIA, collision detection, virtualisation); the library is unstyled; building it would take more than a day; getting it wrong has real accessibility consequences.

**The dividing line: install for correctness, build for expression.** A dialog's focus trap is correctness — use Radix. A hover interaction that is part of your signature moment is expression — build it, or it will look like everyone else's.

**7. Check accessibility before adopting anything.** Keyboard-operate the actual demo. Do not trust the README. Many showcase components are mouse-only and unfixable without a rewrite.

**8. Check performance.** Does it animate compositor-only properties? Does it force layout on every frame? Does it work on a mid-range phone?

**9. If proposing a dependency**, use the G2 format in [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 6, with an honest recommendation. "Build ourselves" is a frequent correct answer.

---

## Done when

The selected rung and rejected alternatives are recorded, the technique is
written down with its source, the build-or-install decision is made with a
reason, accessibility and performance are checked, and any dependency has gone
through G2.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Installing a whole library for one component | Step 5: extract the technique instead |
| Component-library soup — five kits, five visual languages | One token system; libraries are research |
| Adopting a showcase component that is mouse-only | Step 7: keyboard-test the demo yourself |
| Researching an interaction that should be cut | Step 2 comes before steps 3-9 |
| Copying code without understanding it | If you cannot explain the mechanism, do not ship it |
| Building a focus trap by hand | Correctness is exactly what libraries are for |
