# AR-204 — Tool Economics

What a stage can do, what that declaration costs, and what the repository's real
surface justifies.

## 1. There is no function catalogue to trim

Ariadne never hands a worker a list of callable functions with JSON schemas. What
a stage receives is the packet: skills, policy documents, templates and capability
registries, and the worker's own runtime provides the actual read, search, edit and
shell faculties. The honest way to do tool economics here is therefore to measure
the declarations and group them the way the transport already selects them.

## 2. Measured schema sizes

`tooling.pack_sizes` reads the real files:

| Pack | Members | Bytes | Always loaded |
| --- | ---: | ---: | --- |
| core | 5 | 2,896 | yes |
| design | 7 | 36,900 | no |
| research | 5 | 26,970 | no |
| verification | 5 | 33,053 | no |
| writing | 5 | 2,413 | no |
| social | 1 | 8,441 | no |
| capture | 2 adapters | 0 files | no |
| **deferrable total** | | **107,777** | 97.4% of declared bytes |

The core pack is the only one whose members are capabilities rather than files,
and its measured size is the one declaration that has a real path:
`templates/RETURN-HANDOFF.md`. Every other core member is a capability the
worker's runtime already provides, so its declared cost is zero and the pack
records that rather than inventing a schema size.

## 3. What is deliberately not a pack

The brief suggested release and deployment packs. Neither exists here, because
nothing worker-facing implements them: release tooling (`scripts/build-release.py`,
`scripts/install-ariadne-skill.py`) is operator-side and offline, and no stage
declares it. A pack with no member is a fiction with a cost, so it was not
created, and an engine check asserts that it stays absent until a real surface
justifies it.

## 4. Selection, with a reason each time

`tooling.select_packs` is a pure function of the declared stage, the selected
skills and the task's required capabilities. Core is always selected; every other
pack needs a recorded reason. A backend stage at S4B selects core alone and defers
the rest; an S3 task that selected reference research selects design and research
and records why. Two engine checks pin the two ends of that behaviour.

## 5. Discovery stays cheap

Offloading is only safe if the worker can find out that more exists without paying
for it. `tooling.discover` returns a static listing — pack id, title, member ids
and the byte cost of loading each — and it makes no provider call, reads no
project file and opens no network socket. Loading a pack costs one packet section,
which is a transport decision rather than a model request.

## 6. Offload safety, from evidence

Four conditions make a pack unsafe to defer, and `tooling.offload_safety` reports
them from measured rows rather than from intuition:

| Condition | Threshold used |
| --- | --- |
| required on the first turn of most relevant tasks | required frequency at or above 0.5 |
| the model calls it while it is missing | any measured call error rate above zero |
| policy requires it for safe action | declared `policy_required` |
| discovering it costs more turns than loading it | more than one discovery turn |

An unmeasured pack is `UNKNOWN`, never assumed unused. The benchmark exercises
both directions: a frequently required, policy-required pack is refused, and a
rare pack with no errors is reported safe.

## 7. Invariant 41 in code

A required capability that no selected pack provides is refused with a message
naming it. The guard is separate from the selector so a caller that builds a pack
list by hand is held to the same rule, and both a benchmark case and an engine
check assert that the guard fires. Nothing in the economics layer can turn a
missing capability into a cheaper request.

## 8. State of the flag

`tool_loading` defaults to `legacy`: every declared pack stays in the packet, and
the pack machinery is measurement plus a selector the transport can adopt when a
control-versus-candidate experiment supports it. The deferrable share is reported
so a future decision has a number to argue with.
