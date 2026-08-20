# ASSETS: <name>

> Template. Owner: Asset specialist · Stages S3-S4 · Skill: [asset-generation](../skills/asset-generation.md)
> **No project reaches S4 with an unresolved asset on the critical path.**
> Either it exists, it gets made, or the direction changes so it is not needed.

**Last updated:** <date>

---

## Register

> Every asset that ships. Provenance is mandatory on client work, no exceptions.

| Asset | Source | Licence | Dimensions | Format | Weight | Used at | Can ship? |
|---|---|---|---|---|---|---|---|
| | real / generated / stock / drawn | | | | | | yes/no |

## Outstanding

| Asset | Needed by | Plan | Blocking? |
|---|---|---|---|
| | S<n> | real / generate / typographic substitute / cut | yes/no |

> Resolution order, best first:
> 1. A real existing asset
> 2. **A typographic, CSS, or SVG solution** — usually better and always lighter
> 3. A generated asset
> 4. Stock — last, because it is the fastest route to generic
>
> Most asset requests dissolve at option 2.

## Fonts

> The highest visual leverage and the worst licensing risk. See [LIBRARY-POLICY.md](../LIBRARY-POLICY.md) section 9.

| Font | Foundry | Licence type | Cost (INR) | Webfont rights? | Pageview cap? | Licence document |
|---|---|---|---|---|---|---|
| | | <open / commercial / free-personal> | | yes/no | | <where it lives> |

> **Free-for-personal-use fonts are forbidden on client work** without a purchased licence. This is the most common licensing mistake in portfolio-quality work.
> Unlicensed or trial fonts must never reach production. If a licence is pending at G4, the deploy waits.

## Treatment

> What makes mixed-provenance assets read as one system. Untreated assets look pasted in.

- **Crop logic:** <>
- **Grain / texture:** <>
- **Colour treatment:** <duotone / desaturation / none>
- **Mask or border rule:** <>
- **Grid relationship:** <>

## Generation briefs

> Written before generating. Generating without a brief produces something plausible that does not fit the direction — which is worse than nothing, because it is tempting.

| Asset | Subject | Composition | Palette (from `DESIGN.md`) | Treatment | Aspect | Final px |
|---|---|---|---|---|---|---|
| | | | | | | |

## Rules

- **Never ship a grey box or a placeholder.** A QA failure at S5.
- **Never ship generated photography of people** on anything representing a real organisation.
- **Never ship a raster logo** — generate concepts, rebuild as vector.
- Client material does not go to a third-party generator without approval ([PRIVACY-POLICY.md](../PRIVACY-POLICY.md) section 3).
- Per-token generation services are Amber ([BUDGET-POLICY.md](../BUDGET-POLICY.md)) — estimate in INR and ask first.
