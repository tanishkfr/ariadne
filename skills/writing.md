# SKILL: writing

Use this capability when the user wants a creative, academic, scientific/technical,
or human-draft writing artifact. Record one intent and load only its matching
intent guidance. SOCIAL is excluded: use `skills/social-strategy.md` and the
existing `CONTENT-SYSTEM.md` path.

The packet transport maps draft/revision work to S4 and independent editorial
review to S5. Packet preparation proves transport only; a provider transcript is
required before claiming live execution.

The transport entry point is `python scripts/prepare-stage.py prepare-writing`.
Use `--phase draft`, `--phase review`, or `--phase revise`; provide the explicit
intent, request, relevant source files, and criteria. The generated manifest
records provider/model identity, artifact kind, workflow boundary and review
exclusions. It does not invoke a paid provider.

Hard boundaries: preserve supplied evidence, do not fabricate citations or
results, and keep a human draft's ideas and meaningful voice unless the user
requests replacement. Editorial guidance is compact; the model supplies the
judgement.
