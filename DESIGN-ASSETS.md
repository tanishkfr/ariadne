# DESIGN: IMAGES AND ASSETS

Principles and procedure for imagery, texture, and anything that has to be made. Separate from [DESIGN-TASTE.md](DESIGN-TASTE.md) so an asset task does not load the whole taste document.

Register: [templates/ASSETS.md](templates/ASSETS.md) — created only when the design depends on assets that do not yet exist.

---

## Principles

**1. Real over generated over stock.** In that order. Stock is last because it is the fastest path to generic.

**2. No placeholder imagery, ever.** If an image does not exist, either make a real one or change the direction so it is not needed. Grey boxes in a review build are a QA failure.

**3. Images need treatment.** Consistent crop logic, grain, duotone, a border rule, a mask shape, a grid relationship. **Untreated images pasted into a layout look pasted in.** Treatment is what makes mixed-provenance assets read as one system.

**4. Texture is cheap differentiation.** Paper grain, noise, print misregistration, halftone, scanlines. A small amount removes the plastic quality of default web rendering. It must be motivated by the thesis.

**5. Prefer CSS/SVG over raster.** Sharper, smaller, animatable, no licensing question.

**6. Every asset has provenance** — source, licence, dimensions, whether it can ship.

---

## Procedure

**1. Ask whether the asset is necessary.** In order of preference:

1. A real existing asset (client photography, a real screenshot of the work)
2. **A typographic, CSS, or SVG solution** — usually better and always lighter
3. A generated asset
4. Stock

**Most asset requests dissolve at option 2.** A type-led direction removes the dependency entirely, which is one of the main reasons to choose one.

**2. Write the brief before generating.** Subject, composition, palette (from `DESIGN.md`, not invented), treatment, aspect ratio, final pixel dimensions, and where it sits. Generating without a brief produces something plausible that does not fit the direction — worse than nothing, because it is tempting.

**3. Generate in the direction's language.** The asset obeys `DESIGN.md`, not the generator's defaults. If the direction is achromatic and grainy, a glossy full-colour render fails regardless of how good it looks alone.

**4. Treat everything** the same way, per principle 3.

**5. Optimise.** SVG for vector, AVIF/WebP for raster, correct dimensions — never a 3000px image displayed at 600px.

**6. Record provenance.** No exceptions on client work.

---

## Hard rules

**Never ship generated photography of people** on anything representing a real organisation. Generated texture, abstract imagery, and illustration are fine. Generated people and generated evidence are not — it is a credibility risk and, in some contexts, a misrepresentation.

**Never ship a raster logo.** Generate concepts, rebuild as vector.

**Licence everything.** Generated: know the generator's commercial terms. Stock: keep the licence file. Fonts: [LIBRARY-POLICY.md](LIBRARY-POLICY.md) — free-for-personal-use faces are forbidden on client work, and that is the most common licensing mistake in portfolio-quality work.

**Client material does not go to a third-party generator without approval** ([PRIVACY-POLICY.md](PRIVACY-POLICY.md)).

**Per-token generation services are Amber** ([BUDGET-POLICY.md](BUDGET-POLICY.md)) — estimate in INR and ask first.

---

## Asset types, by usefulness

| Type | Notes |
|---|---|
| Texture and grain | Highest value per effort. Often achievable in CSS/SVG. |
| Abstract and backgrounds | Safe to generate, easy to treat into the direction |
| Logo and wordmark concepts | Generate concepts, rebuild as vector |
| Illustration | Works when the direction has a consistent illustrative language |
| Iconography | Prefer drawing to generating; consistency beats variety |
| Photography of real things | Only if it cannot be shot or sourced |
| People | Avoid entirely on anything representing a real organisation |

---

## The blocking rule

**No project reaches S4 with an unresolved asset on the critical path.** Either it exists, it gets made, or the design no longer needs it.

Client assets that "will come later" arrive late or never. Design a fallback at S3 and log the dependency as a risk in `HANDOFF.md`. **A direction that depends on unseen photography is a direction that will be rebuilt.**
