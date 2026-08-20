# SKILL: component-research

**Trigger** — a non-trivial interaction needs building and it is unclear how.
**Owner** — Researcher · **Class** — `R1` + `R4`
**Inputs** — the interaction requirement from `DESIGN.md`
**Output** — a technique writeup in [`RESEARCH.md`](../templates/RESEARCH.md), and possibly a G2 dependency request

**The point of this skill is to take techniques, not dependencies.** Sources in [references/ui-libraries.md](../references/ui-libraries.md) are research-only by default ([LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 4).

---

## Method

**1. State the interaction in behaviour, not implementation.** "A grid where hovering an item pushes neighbours aside with physical weight" — not "a magnetic hover grid". Behavioural descriptions are searchable and do not presuppose a solution.

**2. Ask whether it needs to exist.** Does the thesis require this interaction, or is it decoration? Decoration gets cut here, cheaply, rather than at S5 after it is built.

**3. Find three implementations.** From the research sources, from sites in the wild, from open source. For each: what technique, what it costs, where it breaks.

**4. Extract the technique.** What is actually happening — a transform on a wrapper, an IntersectionObserver, a spring, a canvas layer, a CSS-only trick. Write the mechanism down in `RESEARCH.md` with the source URL. **You are done with the library at this point.**

**5. Decide: build or install.**

Build it yourself when — it is under ~150 lines; it needs to match your tokens; it is visible and judged; a library would impose its own visual identity.

Propose installing when — it solves genuinely hard correctness problems (focus management, ARIA, collision detection, virtualisation); the library is unstyled; building it would take more than a day; getting it wrong has real accessibility consequences.

**The dividing line: install for correctness, build for expression.** A dialog's focus trap is correctness — use Radix. A hover interaction that is part of your signature moment is expression — build it, or it will look like everyone else's.

**6. Check accessibility before adopting anything.** Keyboard-operate the actual demo. Do not trust the README. Many showcase components are mouse-only and unfixable without a rewrite.

**7. Check performance.** Does it animate compositor-only properties? Does it force layout on every frame? Does it work on a mid-range phone?

**8. If proposing a dependency**, use the G2 format in [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 6, with an honest recommendation. "Build ourselves" is a frequent correct answer.

---

## Done when

The technique is written down with its source, the build-or-install decision is made with a reason, accessibility and performance are checked, and any dependency has gone through G2.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Installing a whole library for one component | Step 5: extract the technique instead |
| Component-library soup — five kits, five visual languages | One token system; libraries are research |
| Adopting a showcase component that is mouse-only | Step 6: keyboard-test the demo yourself |
| Researching an interaction that should be cut | Step 2 comes before steps 3-8 |
| Copying code without understanding it | If you cannot explain the mechanism, do not ship it |
| Building a focus trap by hand | Correctness is exactly what libraries are for |
