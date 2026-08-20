# SKILL: asset-generation

**Trigger** — the design needs an asset that does not exist.
**Owner** — Asset specialist · **Class** — `R5`
**Inputs** — asset direction from `DESIGN.md`
**Output** — asset files + [`ASSETS.md`](../templates/ASSETS.md) with provenance for each

---

## Method

**1. Ask whether the asset is necessary.** In order of preference:

1. A real existing asset (client photography, a real screenshot of the work).
2. **A typographic, CSS, or SVG solution.** Usually better and always lighter.
3. A generated asset.
4. Stock. Last, because it is the fastest route to generic.

Most asset requests dissolve at option 2. A type-led direction removes the dependency entirely — this is one of the main reasons to choose one.

**2. Write the brief before generating.** Subject, composition, palette (from `DESIGN.md`, not invented), treatment, aspect ratio, final pixel dimensions, and where it sits in the layout. Generating without a brief produces something plausible that does not fit the direction, which is worse than nothing because it is tempting.

**3. Generate in the direction's language.** The asset must obey `DESIGN.md`, not the generator's defaults. If the direction is achromatic and grainy, a glossy full-colour render fails regardless of how good it looks in isolation.

**4. Treat everything.** Consistent crop logic, grain, duotone, mask, border rule, grid relationship. Untreated assets pasted into a layout look pasted in. Treatment is what makes mixed-provenance assets read as one system.

**5. Optimise.** Correct format (SVG for anything vector, AVIF/WebP for raster), correct dimensions — never a 3000px image displayed at 600px — and a sensible file size against the [QA-POLICY.md](../QA-POLICY.md) budget.

**6. Record provenance in `ASSETS.md`.** Source, licence, dimensions, where used, whether it can ship. **No exceptions on client work.**

---

## Rules

**Never ship generated placeholder photography as if it were real.** A generated photo of a "team" or a "client" on a real business site is a credibility risk and, in some contexts, a misrepresentation. Generated texture, abstract imagery, and illustration are fine. Generated people and generated evidence are not.

**Never ship a grey box.** If an asset does not exist, either it gets made or the design changes. Placeholders in a review build are a QA failure ([DESIGN-TASTE.md](../DESIGN-TASTE.md) section 5.2).

**Licence everything.** Generated assets: know the generator's terms for commercial use. Stock: keep the licence file. Fonts: [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 9.

**Client material never goes to a third-party generator without approval.** [PRIVACY-POLICY.md](../PRIVACY-POLICY.md) section 3.

**Per-token generation services are Amber.** [BUDGET-POLICY.md](../BUDGET-POLICY.md). Ask before spending, with an estimate in INR.

---

## Asset types, in order of usefulness

| Type | Notes |
|---|---|
| Texture and grain | Highest value per effort. Removes the plastic quality of default web rendering. Often achievable in CSS/SVG. |
| Abstract and backgrounds | Safe to generate, easy to treat into the direction |
| Logo and wordmark concepts | Generate concepts, then rebuild as vector. Never ship a raster logo. |
| Illustration | Works when the direction has a consistent illustrative language |
| Iconography | Prefer drawing to generating. Consistency matters more than variety. |
| Photography of real things | Only if it cannot be shot or sourced. Highest risk. |
| People | Avoid on anything representing a real organisation |

---

## Done when

Every asset in `ASSETS.md` has provenance, licence, dimensions, and treatment; every asset obeys `DESIGN.md`; nothing on the critical path is unresolved; no placeholders remain.

---

## Failure modes

| Failure | Countermeasure |
|---|---|
| Generating before checking a typographic solution | Step 1, in order |
| Assets that fight the direction | Step 2's brief comes from `DESIGN.md` |
| Mixed-provenance assets that look mixed | Step 4: treat everything the same way |
| A 4MB hero image | Step 5, against the QA budget |
| Untracked licences discovered at launch | `ASSETS.md` filled as you go, not afterwards |
| Placeholders surviving into review | Blocking QA finding |
