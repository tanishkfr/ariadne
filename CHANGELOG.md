# CHANGELOG

How this system has changed, and why.

**Every retrospective that changes a Builder OS file logs it here.** A retrospective that changes nothing was not a retrospective ([WORKFLOW.md](WORKFLOW.md) S6).

**Name the cause, not just the change.** "Added a check for X" is useless in six months. "Added a check for X because a font licence was discovered at S5 and cost a day" tells you whether the rule still earns its place.

Write the lesson, not the client ([PRIVACY-POLICY.md](PRIVACY-POLICY.md)).

---

## 1.5.3 — 2026-08-23 · ENVIRONMENT AND DISTRIBUTION

V1.5.2 installed a self-contained product, but a fresh user was still routed to
the older `.codex/skills` location unless `.agents` already existed, `doctor`
did not show optional Claude or global-instruction state, and there was no safe
way to opt into general Codex working defaults. The aggregate Windows suite
also exposed a real transient sharing violation while atomically replacing run
state.

Fresh installs now use Codex's documented `.agents/skills` user location while
recognised older Builder OS-managed locations continue in place. A concise
generic baseline can be explicitly installed into the Codex home. Its separate
ownership marker records the canonical source, version and hash; existing
`AGENTS.md`, `AGENTS.override.md`, edited managed instructions, project files
and unrelated configuration are never overwritten. Update and rollback refresh
only an unchanged managed copy, and uninstall removes only owned unchanged
content. Deterministic positive and negative controls cover every branch.

The dependency-free launcher retries bounded Windows sharing violations for
atomic JSON replacement and still exposes persistent denial. `doctor` now
reports Python, runtime, skill, Codex, optional Claude, optional baseline and
project health without inspecting credentials. Release generation adds
versioned release notes and one `SHA256SUMS.txt` inventory covering the runtime,
wheel, descriptor and notes, while retaining source-commit provenance and the
existing clean-tree boundary. The descriptor carries the current publication
state, and the builder cannot emit a publish transition while the licence
boundary is unresolved.

The exact installed-product compatibility fixture now runs in an isolated
system temporary directory because Windows repeatedly held its repository-local
project directory open during cleanup and discarded an otherwise completed
result. V1.5.2 -> V1.5.3 -> V1.5.2 now completes 7/7 without leaving fixture
state behind.

The public licence is not silently selected. Apache-2.0 is the technical
recommendation after inspecting the dependency-free first-party source and
asset boundary, but repository policy keeps that legal decision human-owned.
Until explicitly approved, `Private :: Do Not Upload` remains in package
metadata and V1.5.3 is a packaging candidate, not a publishable release.

**Scope:** no change to `ROUTER.md`, `WORKFLOW.md`, prompts, modes, canonical
design/research/QA/evaluation policy, templates, provider neutrality, gate
semantics, S5 isolation, human approval authority or project-state schema. No
push, tag, release, deployment, provider sign-in or live external task occurred.

---

## 1.5.2 — 2026-08-23 · SOCIAL INTELLIGENCE AND DISTRIBUTION

The earlier optional social method could record a small strategy, but its
project story and visuals were not artifact-backed, voice matching could be
asserted without writing examples, and no durable event connected a planned
post to user-supplied results and a bounded next test. A project that skipped
social work during intake also could not activate the method later without
rewriting evidence history.

V1.5.2 extends the existing content-strategist owner and project-local creative
operations ledger. Contract-version 2 strategies now record research depth,
project evidence, real or explicitly missing visuals, selected and rejected
platforms, current SOURCE -> FINDING -> DECISION trace, optional project-specific
pillars, three to six complete post treatments, voice evidence and falsifiable
hypotheses. Recommendations distinguish documented, observed, researched,
inferred and speculative claims; time-sensitive evidence expires rather than
silently becoming current knowledge.

New `social-result` records accept only artifact-backed, user-provided metrics
or qualitative signals. `social-learning` connects plan, result, bounded
interpretation and one-variable next test in project-local
`CONTENT-LEARNINGS.md`. One result remains inconclusive, a rule needs three
distinct posts, corrections preserve the old result, and dependent learning is
made stale. Five realistic fixture archetypes and negative controls cover weak
assets, late activation, inaccessible or outdated sources, unsupported voice,
generic copy, performance promises, invented metrics and fresh-task recovery.

No platform account, publishing API, scheduler, analytics integration,
database, workflow stage, gate or provider-specific project format was added.
Codex remains the default reasoner; Claude remains optional and externally
unverified. Cursor/Grok implementation routing, S5 isolation and V1.5 human
authority are unchanged.

---

## 1.5.1 — 2026-08-23 · OPTIONAL CLAUDE REASONER

V1.5 had one verified reasoning path and provider-neutral project documents,
but no durable way to select, switch or recover a second reasoning provider.
V1.5.1 adds an adapter-owned reasoner capability contract with Codex as the
unchanged default and Claude as explicit opt-in. Claude is not a dependency,
is not installed by normal setup, and remains execution-unverified on the
validation machine because its CLI is absent.

Reasoning packets for S1, S2, S3, S4A, S5 and S6 now inherit the recorded
reasoner. S4B remains controlled by the existing implementation handoff and
provider preflight. A pre-output provider switch creates an immutable linked
same-stage child; a post-output switch waits for the next reasoning boundary.
Failures become parent evidence. Codex fallback occurs only when no material
current-stage output exists; otherwise the controller preserves the partial
work and stops for human judgement. Rejected-direction context, S5 isolation,
partial implementation returns and both switch directions have deterministic
positive and negative controls.

An optional thin Claude user skill operates the same controller and generated
packets without copying policy or creating project `CLAUDE.md`. `builderos
enable-claude` feature-detects the CLI and installs only that managed skill;
`disable-claude` removes it. Normal install, Codex skill, project files, gates,
canonical handoffs and Cursor/Grok implementation routing remain unchanged.

**Scope:** no change to `ROUTER.md`, `WORKFLOW.md`, modes, prompts, canonical
design/research/QA/evaluation policies, templates, S5 isolation, human approval
authority or project-state schema. No Claude command, authentication, live
session, provider install, remote push or deployment was performed.

---

## 1.5.0 — 2026-08-23 · REAL-PROJECT CREATIVE PRODUCTION

Builder OS could already install, transport verified stage context and preserve
human gates, but real-project operation still hid two practical weaknesses:
human interruptions were counted without separating routine machinery from
creative authority, and a rejected pre-G1 direction required the operator to
reconstruct the reason and continuation context manually.

V1.5 makes the human-intervention budget operational with explicit categories
for setup, file movement, prompt discovery, routine confirmation, creative
decisions, external-provider launches and review decisions. Project status now
reports mechanical work separately from creative authority and external
actions. It also reports the latest evidenced creative-review strengths,
weaknesses, priority and iteration state without turning internal review into a
gate approval.

The creative-operations ledger now requires complete implementation mappings,
observed positive controls for verified visual evidence, explicit drift for
every approved requirement, linked review iterations, do-not-change boundaries
and a fixed two-iteration stop. Five realistic fixtures exercise minimal work,
ambitious provider limits, non-destructive adoption, conflicting references and
explicit social activation, including non-success branches.

A new `restart-direction` runtime path preserves the rejected `DESIGN.md` and
the human's reason verbatim, records complete S3 execution without approving
G1, and creates a non-overwriting same-stage child. The child carries the exact
previous reference and conditional design inputs plus hashed restart evidence;
missing, changed or out-of-boundary restart context fails deterministically.

The executable-skill checker now requires explicit trigger, input, output and
done/stop contracts for every selected method. Runtime and packet controls cover
skill drift, partial implementation, unobserved visual claims, missing drift,
review parentage, iteration limits and restart provenance with positive and
mutation controls.

**Scope:** `ROUTER.md`, `WORKFLOW.md`, modes, prompts, canonical design/research/
QA/evaluation policies, templates, provider neutrality, gate semantics and S5
isolation are unchanged. Tightening internal creative-review readiness into a
hard S5 prerequisite was explicitly rejected for V1.5: readiness remains a
strong warning/recommendation unless the existing workflow already requires
more. A stricter boundary is only a later candidate after real-project evidence,
not an approved change. Cursor was unavailable. No dependency install, remote
push, deployment, credential access or historical validation rewrite occurred.

---

## 1.4.0 — 2026-08-23 · INSTALLABLE USER-LOCAL PRODUCT

Builder OS previously had a capable runtime and managed Codex entry skill, but
a new user still needed the source checkout and a maintainer-only skill script.
That made the logical workflow usable while leaving distribution, repair and
first run as manual operator work.

V1.4 adds a dependency-free Python launcher and deterministic wheel. The wheel
carries a generated runtime bundle whose files and source commit are recorded in
one release manifest; it is an immutable transport copy of the existing
canonical sources, not a new policy owner. Installation chooses a platform-
appropriate user-local directory, verifies every hash, atomically activates a
version, and installs the managed `$builderos` skill with an exact runtime
pointer. No canonical file is copied into a project.

The launcher now provides one authoritative `VERSION`, idempotent install and
repair, HTTPS/checksum updates, retained-version rollback, plain-language
diagnostics, compatibility checks and project-preserving uninstall. Update and
skill swaps restore the previous valid state when activation is interrupted.
Unsafe archive paths, corrupted files, unmanaged skill directories, unknown
skill files and incompatible launcher/project schemas are rejected.

A realistic offline stranger test builds the wheel, installs it into a clean
Python environment, activates its embedded runtime, starts an ordinary-language
project without the checkout, diagnoses the installation and uninstalls while
preserving project source and history. Deterministic lifecycle tests cover
Windows/macOS/Linux path selection plus install, repair, update, rollback,
network, permission, checksum, traversal and compatibility failures.

The README and short install/update/troubleshooting guides now lead with the
user experience. The old checkout skill installer remains available only for
maintainers. Public publication is deliberately withheld: the repository has no
approved public licence and release creation needs explicit human authority.

**Scope:** routing, workflow gates, policies, modes, templates, provider
neutrality, independent-review isolation and human approval authority are
unchanged. No remote push, deployment, project rewrite or historical-evidence
edit occurred.

---

## 1.3.0-rc.1 — 2026-08-23 · CREATIVE OPERATIONS WITH RENDERED EVIDENCE

V1.2 could prove research inspection and trace it into a locked design, but it
did not carry that design through implementation and rendered behaviour. A
technically complete build could therefore preserve the files while losing the
thesis, responsive transformation or signature interaction. Operator effort
also still mixed necessary human authority with avoidable return handling.

New projects now gain one post-G1 project-local creative-operations ledger. It
derives testable requirements from approved project documents, hashes their
source anchors, maps them to implementation, generates a thesis-first visual-QA
plan and records source inference, rendered evidence, observed interaction,
verification and environmental blockers separately. Drift is independently
classified as approved, allowed, drift or unknown.

An internal creative-review method judges ten project-quality dimensions from
recorded evidence and produces one highest-value improvement plus a do-not-
change boundary. It cannot change the locked direction, approve G3 or enter the
isolated S5 packet. The S4B contract and provider adapters now deliver the
operations plan and canonical visual-QA method.

Every S4B packet also names a unique project-local structured-return target.
The manifest verifier rejects missing, duplicated, stale, escaped or wrong-ID
targets; retries cannot overwrite earlier evidence. The controller ingests only
the current packet's return, while manual ingestion remains a recovery path.
Runtime state separately classifies necessary, valuable, avoidable,
unacceptable and prevented human interventions.

An optional social-strategy skill and template activate only on an explicit
request. Documented platform advice needs a dated inspected source; inferred
and speculative recommendations remain labelled. The method requires three
project-specific concepts, timing as a test, measurement and revision lineage,
rejects common generic AI openers, and never posts or authenticates.

The isolated Signal Atlas fixture was actually rendered and interacted with at
1280px, 768px and 375px. It preserved the approved signature at wide and narrow
widths, exposed a real tablet drift, and kept reduced-motion behaviour
unverified because the available browser could not emulate it. A LinkedIn-only
social strategy used two inspected current help pages and the observed drift;
no platform result was fabricated.

**Scope:** `ROUTER.md`, `WORKFLOW.md`, modes, gates, canonical design/research/
QA/evaluation policies, human authority and S5 isolation are unchanged. Limited
subagents and provider automation are recommendations only. Cursor was
unavailable; no provider automation, dependency install, remote push,
deployment, credential access or historical-evidence rewrite occurred.

---

## 1.2.0-rc.1 — 2026-08-23 · CREATIVE INTELLIGENCE WITH OBSERVED EVIDENCE

V1.1 could reliably route, transport, resume and preserve stage evidence, but it
could not durably distinguish a recommended creative method from one that ran,
or a supplied URL from a reference that was actually inspected and used. A
well-worded `DESIGN.md` could therefore assert its own research history.

New projects now receive one project-local creative evidence ledger after S1.
A reasoned assessment chooses minimal, standard or deep research and selects
only relevant capabilities. Each selected method records why it was chosen,
the question it answers, its inputs, expected output, whether it is mandatory,
and strict recommended → invoked → completed → used evidence. Skips, failures,
and not-useful outputs remain explicit.

Reference records distinguish found, inspected and inaccessible sources.
Inspection needs a non-empty hashed retrieval/visual artefact, concrete
observations, at most two transferable mechanisms, and explicit borrow/reject
decisions. Downstream design decisions must cite inspected records and exact
anchors in hashed project artifacts. Resource comparisons additionally retain
capability, fit, compatibility, licence, cost, alternatives, necessity and the
resulting decision without installing or approving anything.

S2 and S3 packets carry this ledger when present; legacy runs remain readable,
and isolated S5 receives none of it. Pre-G1 checks reject generic thesis words,
missing signature/mobile behaviour, incomplete ten-question checks, cosmetic
alternatives, uninspected reference claims, stale artifacts, hand-edited skill
histories, and unsupported resource claims. Provider status separately reports
selection, observed/reported execution, and successful return.

A realistic Living Margins fixture loaded and visually or interactively
inspected three live references, preserved captures, synthesised a conflict,
compared two materially different directions, traced three decisions and
stopped at human G1. A separate minimal fixture chose no extra research and was
rediscovered from only its project path in a fresh process. Synthetic controls
cover technical resource selection, inaccessible and unused sources, conflicts,
generic direction rejection, continuation and stale evidence.

**Scope:** `ROUTER.md`, `WORKFLOW.md`, modes, canonical design/QA/research/
evaluation policies, templates, gate authority and S5 isolation are unchanged.
No dependency was installed; no provider was executed; no gate was granted; no
credential, remote, deployment, production state or historical evidence was
changed.

---

## 1.1.0-rc.1 — 2026-08-23 · PRODUCT INTELLIGENCE AND SAFE ADOPTION

The V1 runtime made canonical delivery reliable, but a real returning operator
still received a thin stage-oriented status, an implementer could be handed an
under-specified `HANDOFF.md`, partial external work required knowledge of a
low-level retry command, concurrent self-tests collided, and existing projects
could not enter the product at all.

Builder OS now derives a calm project briefing and health map from canonical
project documents, packet lineage, provider preflight, structured returns, QA,
and append-only evidence notes. It reports the complete goal, approved direction,
current work, attention items, and the next human decision without becoming a
second policy owner. Durable notes distinguish verified, reasonably assumed,
externally unverified, and blocked facts.

The S4 boundary now fails closed on missing outcome/acceptance criteria, content
readiness, implementer discretion, thesis drift, success-criteria drift,
unapproved dependencies, unresolved critical assets, incomplete provider routing,
or a missing return contract. The existing `HANDOFF.md` template and S4A prompt
own those missing transport fields; the underlying design, QA, routing, and gate
policies are unchanged. Structured returns also gain a deterministic JSON view
for re-entry while preserving the provider's Markdown report.

The public `advance` command now records obvious same-session output, prepares
routine continuation, and automatically creates a non-overwriting S4B child when
an external return is partial or blocked. Complete returns remain the positive
control and reach isolated S5 only when mechanical QA exists. Provider preflight
recommends the recorded fallback or a bounded split instead of only naming a
failure.

Existing repositories can opt into `start --adopt-existing`. Adoption inspects
the live project read-only during S1, preserves every existing file and current
behaviour, records its provenance, and refuses to overwrite `PROJECT.md` or
`AGENTS.md`. Ordinary start still refuses a non-empty directory. The entry skill
and operator guides expose this as an optional migration path, not a silent mode.

Independent runtime, packet, and installer self-tests now use unique
Windows-compatible workspaces, closing a reproduced concurrent-suite collision.
The realistic Memory Atlas journey reached S2 and S3 without manual packet work,
then stopped correctly at human G1. A genuinely fresh Codex task rediscovered the
run and reported the full status with zero prompt, packet, hash, transcript, or
run-path lookup. A current Test B Cursor S4B packet verifies against this release;
Cursor was not opened and complete live provider return remains unverified.

**Scope:** `ROUTER.md`, `WORKFLOW.md`, modes, canonical design/QA/research/
evaluation/privacy policies, human gate authority, provider-neutral capability
routing, historical evidence, production state, and remotes are unchanged. No
dependency was installed, no credential was accessed, and nothing was pushed or
deployed.

---

## 1.0.0 — 2026-08-23 · CALM RUNTIME AND RECOVERABLE PROVIDER HANDOFFS

Test B established that Builder OS's standalone delivery contracts could be
correct while the product remained tiring to operate. The user still had to
find prompts, construct and verify continuations, track evidence paths, re-enter
provider routing, discover provider limits mid-build, carry state back from an
external builder, and paste an independent judgement into `QA.md`. Test B also
proved that a fresh Cursor/Grok implementation session could consume the S4B
handoff and begin work; provider quota ended the run before a complete return.
That evidence is preserved as a provider limitation, not rewritten as success.

Builder OS now has a thin runtime controller and a repo-scoped Codex entry skill.
The controller starts or discovers a project run, refuses ambiguous histories,
selects the next valid boundary from project state, delegates packet provenance
to `prepare-stage.py`, records structural or verbatim evidence honestly, and
writes a human-readable operations log. An explicit stage argument can only
confirm the inferred next stage or request a same-stage retry; it cannot bypass
G1 or another gate.

S4A's canonical `HANDOFF.md` now records capability, provider, model, effort,
workload, split, and reason. Runtime preflight reads that record and handles
verified, reasonably-assumed, human-check-required, blocked, and internally
retained work without inventing availability or quota. A canonical structured
return contract carries completed work, files, decisions, deviations,
dependencies, tests, evidence, gaps, and the exact resume point. Complete
returns can reach isolated review; partial/blocked returns create a new S4B
child and preserve the earlier attempt.

Independent S5 responses now have a deterministic ingestion boundary. Builder
OS preserves the raw response byte-for-byte, validates the marked judgement,
and replaces only the judgement region of `QA.md`. Missing markers,
placeholders, missing independence attestation, invalid recommendations, and
duplicate ingestion fail closed. Reviewer scores, verdicts, findings, and
evidence limitations are never paraphrased.

The managed personal skill installer records the canonical checkout, detects
drift, and refuses to overwrite an unmanaged skill. Operator documentation now
starts with `$builderos`; stage commands remain documented only as recovery
tools. The runtime dry run covers S1 -> S3 -> G1 -> S4A -> provider preflight ->
S4B partial retry -> complete return -> isolated S5 -> review ingestion.

**Canonical ownership and gates:** `ROUTER.md`, `WORKFLOW.md`, modes, design/QA/
research/evaluation policies, and human gate authority are unchanged. Generated
packets, state, logs, and installed skill copies are transport/runtime artifacts,
not new policy owners. No remote push, deployment, credential access, production
action, or historical-evidence rewrite occurred.

---

## 0.3.6 — 2026-08-22 · V1 STAGE TRANSPORT AND CONTINUATION HARDENING

The A3R1 exercise proved that correct standalone delivery contracts were still
painful to operate: the operator manually found canonical inputs, concatenated
multi-file packets, created continuation records, chose evidence paths, preserved
parent hashes, and rebuilt S5 isolation by hand. That repeated work is now owned
by `scripts/prepare-stage.py`, a transport helper rather than an orchestrator or
policy system.

The helper prepares S1, conditional S2, S3, S4A, S4B, isolated S5, and S6. Every
generated continuation has an explicit parent, source commit, per-source SHA-256,
conditional-input decisions, an expected transcript path, and a machine-readable
manifest. Preparation refuses existing output directories, packets inside the
project, real project packets inside Builder OS, wrong or same-stage parents
without an explicit retry, and parents whose transcript is missing. Verification
fails when a canonical or project input, parent manifest, parent transcript,
packet section, stage, or S5 delivery set has drifted.

Two deterministic stage-input gaps were closed. Conditional S2 had an adapter
delivery row and canonical policy/template but no pasteable entry point; the new
`prompts/research.md` executes the existing conditional stage without changing
its policy or adding a gate. S6 produced `RETROSPECTIVE.md` but neither its prompt
nor adapter delivered `templates/RETROSPECTIVE.md`; both now do. Canonical policy
and template ownership is unchanged.

`scripts/check.py` now checks nine standalone prompt contracts, five chained
prompt transitions, the packet transport map, S4A→S4B parent order, S5 isolation,
and S6 template delivery. Its self-test adds positive controls and negative
mutations. The packet helper's own 20-case self-test covers a synthetic
S1→S2→S3→S4A→Cursor-labelled S4B→S5→S6 chain plus stale sources, changed parent
evidence, missing sections, wrong stage/parent, missing evidence, duplicate
continuations, and forbidden S5 context.

Operator documentation now describes generated transport and removes stale
machine-specific setup claims. Cursor has a concrete validation handover, but was
not opened or run; packet generation proves readiness to test, not provider
behaviour. No remote push, deployment, production action, credential access,
gate approval, validation-evidence rewrite, routing change, or workflow-gate
change occurred.

---

## 0.3.5 — 2026-08-21 · STANDALONE STAGE DELIVERY-CONTRACT REPAIR

A3 exposed the first deterministic standalone-input defect at S1. The bounded
S0-S6 delivery audit performed before resuming A3R1 found the same root cause at
later boundaries: several pasted stage prompts named canonical Builder OS files
that a fresh project session was never instructed or equipped to receive. Some
blocked paths could also print the next stage, and S5 could proceed directly to
G4 without first presenting the combined mechanical and independent evidence at
human-only G3.

The affected prompts now declare **REQUIRED INPUTS** and an in-fence **IF MISSING**
contract. A missing input stops in the same stage, names the gap, forbids partial
outputs, and emits a same-stage retry rather than a forward transition. Provider
adapter matrices now deliver the existing canonical skill, policy, rubric, and
template files transiently to the sessions that consume them. They are not copied
into project repositories and their ownership is unchanged.

S4A now explicitly hands off to S4B. S4B distinguishes an already-connected
feature-branch preview from push, merge, connection, and production actions using
the existing `WORKFLOW.md` rules. S5 emits a paste-ready independent judgement
block for `QA.md`, presents G3 first, and permits a G4 request only after explicit
human G3 approval. S6 consumes those persisted findings from `QA.md`. Content
drafting and weekly review now declare voice, pillars, and current learnings as
continuity inputs instead of relying on conversation history.

`scripts/check.py` guards all eight affected prompt boundaries and both adapter
matrices. Its self-test includes repository and harmless-change positive controls
plus negative mutations for an out-of-fence manifest, missing blocked behaviour,
forward transition while blocked, missing canonical QA delivery, reversed G3/G4
order, missing QA judgement persistence, adapter omissions, and missing content
continuity.

**Scope:** no routing rule, workflow rule, mode, skill, canonical design/QA/
research/evaluation policy, template, validation protocol, or validation run was
changed. A3R1 was not resumed and A4 was not created.

---

## 0.3.4 — 2026-08-21 · A3 DETERMINISTIC S1 INPUT-CONTRACT REPAIR

A3 exposed a deterministic defect before S1 could write its first document. The
standalone test project correctly contained only `.git` and `.gitignore`, while
`prompts/project-start.md` required the session to generate root `AGENTS.md` from
`templates/AGENTS.md`. The pasted prompt neither contained that template nor gave
the standalone session a path or mechanism to reach the Builder OS repository.
Codex stopped rather than inventing the missing contract; no project document was
created and S3 was not started.

The S1 fenced prompt now carries an exact **non-canonical transport mirror** of
`templates/AGENTS.md`. The template remains the sole canonical owner. The mirror's
nested Markdown code fences use tildes so they cannot close the outer pasted prompt;
otherwise the transported contract is exact. This preserves the standalone-project
model without adding an initializer, attachment step, or test-only exception.

`scripts/check.py` now compares the mirror against the canonical template's
deterministic transport form. Its self-test includes three positive controls and
four negative cases: canonical-only drift, prompt-only drift, a mirror outside the
S1 fence, and a missing mirror. A paired canonical-and-mirror update must pass, so
the guard cannot succeed by discarding its inputs or hard-coding today's content.

**Scope:** `templates/AGENTS.md`, routing, stages, setup scripts, and every unrelated
frozen-core file are unchanged. A3 remains stopped at S1; this repair has not been
used to resume it or start A4.

---

## 0.3.3 — 2026-08-21 · V1 CANDIDATE · CORE FROZEN

The three runtime items from the certification audit. **No core changes.** No new modes, skills, roles, policies, or documents.

### Project AGENTS.md is now the runtime state file

`templates/AGENTS.md` rewritten around the `AGENTS.md` open standard — stewarded by the Agentic AI Foundation, auto-discovered by Codex, Cursor and 20+ other tools. It ships into a project repo where Builder OS is absent, so it carries compact reminders rather than pointers.

**It is canonical for exactly two things: `Current state` and `Do not change`.** Everything else mirrors `PROJECT.md` and `DESIGN.md`. The file states its own non-canonical status, and the direction of change is one-way: edit the canonical document first, then update the runtime. A decision that exists only in `AGENTS.md` is a decision nobody recorded.

### Current state is persisted, in one place

Stage · last gate passed · next stage · next prompt · updated date. **No new document, no state machine, no database — plain text in the file every tool already reads.**

Ownership is explicit, because a gate an agent records for itself is not a gate:

| Who | When |
|---|---|
| S1 session | generates the file |
| **You** | **at G1 and G3** |
| S4 session | both ends |
| S6 session | closes it out |
| S5 reviewer | **never** — it would leak the build context the review exists to withhold |

### Generation wired at the earliest reliable point

Traced the prompts: `PROJECT.md` and the routing decision exist at the end of S1; the thesis does not exist until S3; commands do not until S4. So the file is generated at **S1** with the direction section explicitly pending, then updated as the project moves. **No fake or mostly-empty file is ever written**, and S3 deliberately writes nothing — it emits a block for you to paste on approval, so a rejected direction never claims a gate it did not pass.

### Checks

`check.py` gained a structural guard: required state fields, well-formed stage and gate identifiers, an explicit non-canonical declaration, and detection of canonical policy blocks pasted in wholesale. **All three paths negative-tested.**

**That negative test found a real defect in my own guard.** The patch script that wrote the checker interpreted `\b` as an escape, so two regexes contained literal backspace bytes (`0x08`) and could never match — the malformed-identifier check silently passed everything. Repaired at byte level and re-tested. *A check that cannot fail is worse than no check, and this one nearly shipped that way for the second time in this project's history.*

### Simulated — requires Codex/Cursor

Seven state transitions traced against the written prompts: **7 pass, 0 fail, 1 documented caveat.** Between G3 and the retrospective the stage still reads S5, because the reviewer is forbidden from touching project records. Recorded as expected behaviour rather than given its own mechanism. Full trace in [tests/validation-protocol.md](tests/validation-protocol.md).

**This is not provider validation.** It proves the state mechanism is internally unambiguous, not that any tool honours it.

### Deliberately not built

A Builder OS skill — it would duplicate the `AGENTS.md` standard and work in one vendor's product instead of twenty-five. Cross-product automation — nothing drives Codex and Cursor from one controller. `.builder-os/` context packets — the four required documents plus the runtime file already are the packet. Router split · frame changes · print mode · QA reorganisation · new scripts.

### Status

**V1 CANDIDATE. Core frozen.** The next change must come from Test A, Test B, or a real project — not another audit.

---

## 0.3.1 — 2026-08-21 · READY FOR V1 VALIDATION

Four structural blockers from the V1 readiness review, closed. **No redesign.** No new modes, skills, roles, or frameworks.

### P0.1 — Stage entry gap closed

v0.3 had entry points for **2 of 7 stages**. S3 — design direction, the stage the whole system exists to protect — had none. You were expected to know to open `skills/design-direction.md`, read `templates/DESIGN.md`, and compose your own prompt.

Added [prompts/design-direction.md](prompts/design-direction.md), [prompts/build-kickoff.md](prompts/build-kickoff.md), [prompts/retrospective.md](prompts/retrospective.md). Each stage now **ends by naming the next entry point**, and [WORKFLOW.md](WORKFLOW.md) carries an entry-point column so a future gap is visible in the stage table itself.

*Cause: the readiness review traced the first 30 minutes literally and found design thinking beginning at minute 30 with no support. The predicted failure was pasting DESIGN-TASTE into a chat and skipping reference analysis, the thesis test, and G1 — the three mechanisms that prevent generic output.*

### P0.2 — Router regression suite restored

[tests/router-cases.md](tests/router-cases.md): **42 cases across 8 categories**, each citing the rule that justifies it, with an append-only result log.

`check.py` now guards its structure — categories present as headings, rules canonical, modes not deleted, run history intact.

**The guard was vacuous on first write and a negative test caught it.** The category check matched substrings anywhere in the file, so a renamed heading passed; and the rule-ID regex was too narrow to match a deliberately malformed ID, so a fabricated rule reference was reported valid. Both fixed, then re-tested: the guard now fails on both.

*Cause: v0.2 deleted `validation/` for having no consumer. Right about dry-run narratives, wrong about executable test cases — their consumer is every future router change.*

### P0.3 — Learning loop closed

**A retrospective no longer edits Builder OS.** It produces proposals; you approve them.

Four qualification tests (recurs · evidence · names a specific rule · survives the deletion test) and a change-proposal format in [templates/RETROSPECTIVE.md](templates/RETROSPECTIVE.md); approval, regression and freeze thresholds in this file. Deletions are proposable and explicitly encouraged. **No new document.**

*Cause: the loop was "edit the file and log it" — an instruction, not a loop. Nothing distinguished a system-level lesson from a project annoyance, which is the mechanism that produced 71 files.*

### P0.4 — Three safety ambiguities resolved

Worktrees: creation Green, **two agents on one branch Amber**. Preview deploys: Green once connected, **connecting the repo is itself Amber** — an external-account action. Analytics: **instrumentation is Amber, pasted numbers are Green** — one word, two actions, now named separately.

### Not done, deliberately

No visual regression · no project-level automation script · no product-app validation · no adapter verification beyond one provider · no template trimming. Each is deferred pending evidence, per the thresholds above.

### Status

**READY FOR V1 VALIDATION.** Structural work is complete and mechanically verified. **Zero real projects have run through this system.** The three tests in [tests/validation-protocol.md](tests/validation-protocol.md) are what earn v1.0.0 — nothing before them is evidence about real work.

---

## 0.3.0 — 2026-08-21

**The router now routes on intent, not keywords.** The v0.2.1 stress test failed 4 of 8; the failures were not eight bugs but four structural causes, and patching phrases would have produced a longer keyword table with the same defect.

### Why the old model failed

| Cause | Consequence |
|---|---|
| Signals were **nouns**; modes are **workflows** | "portfolio" appears in create-the-site, create-something-for-it, and review-it. One noun, three workflows, no way to separate them. |
| Artifact presence was an **override**, not an input | An existing thing can be a `subject`, a `source`, or a `reference`. Collapsing all three forced builds into reviews. |
| Confidence counted **keyword tidiness** | One matching keyword = HIGH by construction. This is the mechanism that manufactured confidently-wrong routes. |
| "Mode" was the router's **only vocabulary** | Restart had nowhere to attach, so nothing routed to it. Accepted-patterns had no way to express intent, so it reached for quantity as a proxy. |

**Root cause: the router computed an answer without ever representing the question.**

### The new model

`message → FRAME (10 slots) → routing rules → mode + confidence → ask / assume / proceed`

Two slots carry the redesign. **`ARTIFACT` holds a role** (subject / source / reference) rather than a boolean, which dissolves the build-vs-review confusion with no keyword list. **`OBJECT` can be `UNRESOLVED`**, which forces LOW confidence mechanically — closing the confidently-wrong failure mode by construction rather than by vigilance.

### Rules, now with canonical IDs

`R-ACT-1` action priority · `R-REF-1` references modify, never select · `R-REF-2` replication routes to CREATE, originality is a design conversation · `R-XFM-1` transformation routes by target · `R-DEST-1` destination is not object · `R-INT-1` restart is an interrupt · `R-PAT-1` accepted patterns by intentionality · `R-CONF-1` confidence from unresolved · `R-ASK-1` fewest highest-impact questions.

Referenced by ID elsewhere instead of paraphrased. `scripts/check.py` verifies every ID is defined and no reference dangles — it does **not** check that a rule still means what a referencing file assumes. Only reading catches that.

### Removed

The §3.1 signal table · tie-break 1 (artifact→audit-review) · tie-break 3 ("offering the two candidates", which never fit a five-way blank) · signal-count confidence · **the numeric cap on accepted patterns** · the per-mode `Signals:` keyword lists in all five mode files.

### Accepted patterns — cap replaced by intentionality

The "maximum three" cap blocked a deliberate request for a glassmorphic card dashboard, and its count was undefined at the boundary. Removed entirely. A pattern is accepted when the reason is conceptual, narrative, functional, historical, medium-specific, or interaction-based — not preference. **Multiple are allowed.**

Not a loophole: accepting the *pattern* does not accept the *execution*. The reviewer still rejects it when the claimed rationale is not visible in the result — a stronger check than a count, which only ever measured how many rules you broke and never whether you meant it.

*Cause: "SaaS dashboard, 17 cards, glassmorphism" — the escape hatch built to stop the system fighting the user just moved the fight from one pattern to four.*

### Found by the new adversarial matrix

Two gaps the redesign itself introduced, caught before shipping:

- **`EXTEND` re-derived a mode.** Adding a leaderboard to a game would have classified it as a product app. EXTEND now inherits the current project's mode; only a real scope change re-routes.
- **`ANALYZE` with no subject had no destination.** "Which CMS should I use?" fell through. It is now a research question, not a project — audit-review needs something concrete to judge.

### Stale references repaired

Precedence moved section 8 → 12 and mode-switching 3.4 → 3.6; four files still pointed at the old numbers. Converted to rule IDs where an ID exists, which is what the IDs are for.

### Known limits

1. **Still never used on a real project.** The matrix tests the written rules, not a running agent.
2. **I wrote the router and I ran its tests.** That violates the independence rule this system enforces everywhere else. The mitigation is that every result quotes the rule it came from, so the reasoning is checkable rather than trusted.
3. **The frame is a reasoning protocol, not a parser.** It works if the agent fills the slots honestly. An agent that writes a confident `OBJECT` where the request was vague defeats R-DEST-1 — the same class of failure as a dishonest scorecard.

---

## 0.2.1 — 2026-08-21

Router stress test run against the eight cases in section "Week 3" below. **3 PASS, 4 FAIL, 1 FRICTION.** Fixes applied to what was authorised; the routing failures are recorded here undecided.

### Fixed

- **game-experiment input/display defaults.** Question 2 had a default of "keyboard and mouse, desktop-first" and the assumptions table said "desktop-first". For an installation or a phone piece every one of those is wrong, and the router batches questions *with defaults* so "all defaults" silently produced a desktop build. Question 2 now has **no default**, and installations route here explicitly rather than needing a sixth mode.
  *Cause: stress case 6, "make this into an interactive installation". Confirmed by inspection — the three physical projects in this workspace are all web tech (Capacitor, kiosk browser), so the gap was the defaults, not a missing mode.*
- **Secret protection documented as portable and manual** ([QA-POLICY.md](QA-POLICY.md) section 9). Hooks in `.git/hooks` do not survive a clone, so the hook lives in a committed `.githooks/` directory and `core.hooksPath` is set per clone. `templates/AGENTS.md` now carries a **status line stating whether it is installed**, because nothing installs it automatically and an agent must not assume a net exists.
- **Scorecard leftovers from 0.2.0.** `skills/design-direction.md` still instructed a self-scored G1 with a "below 35" threshold, directly contradicting the 0.2.0 change; `templates/DESIGN.md` still carried a `Scorecard: <n>/50` field directly above a section reading "not scored". Also a stale section reference.
  *Cause: found while trimming DESIGN.md. The duplicate-sentence checker cannot catch a contradiction between two differently-worded rules — only a human reading can.*

### Known failures, not yet fixed

1. **Tie-break 1 is too aggressive** ([ROUTER.md](ROUTER.md) 3.2). "An existing artifact is supplied → Audit/review, unless the request says rebuild or redesign." The exception list is missing `like`, `inspired by`, `in the style of`, `into`, and `based on`. Causes 2 of 8 failures: "build something like Burocratik" and "make this into an installation" both route to critique instead of build.
2. **Accepted-pattern counting is undefined** ([ROUTER.md](ROUTER.md) 10). "SaaS dashboard with 17 cards and glassmorphism" is either 3 acceptances (proceeds) or 4 (router halts) depending on how rows are counted. At the boundary the escape hatch re-creates the fight it was built to end.
3. **"portfolio" does not distinguish container from contents.** "Something cool for my portfolio" scores one clean signal → High confidence → builds a website, when it probably meant a piece to put in one.
4. **Nothing routes to the restart procedure.** Section 11 is complete but no signal fires on "scrap the direction"; you only reach it by knowing it exists.

---

## 0.2.0 — 2026-08-21

Restructured after an independent audit of v0.1.0. **71 files to 49.** No rule was lost; several got one home instead of four.

### Behaviour changes

- **Scorecard moved out of the author's session.** Self-scoring a direction you just wrote clusters at 4 and measures nothing. Scoring now happens at S5 by a Reviewer with no build context, and **every score below 4 must cite a specific comparison** that does it better. G1 uses a qualitative 10-question check instead.
  *Cause: the audit could find no mechanism preventing a generous 44/50 every time, which invalidated the primary quality claim.*
- **Added accepted patterns** ([ROUTER.md](ROUTER.md) §10). A blocking anti-generic pattern can be chosen deliberately — declared in `PROJECT.md` before it is built, with a reason, maximum three. It drops to a Note and stays visible.
  *Cause: stress-testing "build a SaaS dashboard with 17 cards and glassmorphism" showed the system would block a build the user explicitly asked for. The rules assumed genericness always came from the tool.*
- **Added direction restart** ([ROUTER.md](ROUTER.md) §11): what survives, what dies, and a requirement to write down why the old direction failed before writing the new one.
  *Cause: the most common creative event had no defined path, so the default was quietly patching a dead direction.*
- **Required document set cut to four** — `PROJECT`, `DESIGN`, `HANDOFF`, `QA`. Everything else is conditional with a stated trigger.
  *Cause: `TASKS.md` and `ASSETS.md` on a two-day experiment are ceremony.*

### Structural changes

| Change | From | To | Cause |
|---|---|---|---|
| Roles | 12 | 5 | Accessibility, performance, and portfolio "roles" were already review lenses. **A lens is not an agent.** |
| Review lenses | 9 | 5 | Conversion pulled toward the SaaS patterns the system rejects; accessibility and performance moved to mechanical QA |
| Modes | 7 | 5 | `benchmark` had no routing behaviour — it is a maintenance activity, now in this file. Client and portfolio differed by a flag, not a mode. |
| Skills | 16 | 5 | Nine were checklists or restatements wearing a skill header. Kept only files containing a method you could not derive from a policy. |
| Reference files | 4 | 2 | Two had zero inbound links |
| Automation | none | `scripts/check.py` | The link checker had already caught 7 real bugs during construction — demonstrated benefit, not speculative |

### Deleted

`examples/` (4) and `validation/` (4) — 8,871 words consumed by no workflow stage. `AGENT-ROLES.md` and `AUTONOMY-POLICY.md` folded into `WORKFLOW.md`. Nine skills folded into the policy documents that already owned their rules. `modes/benchmark.md` folded into this file.

### Split

`DESIGN-TASTE.md` into three, so a motion task loads ~900 words instead of 2,652: [DESIGN-TASTE.md](DESIGN-TASTE.md), [DESIGN-MOTION.md](DESIGN-MOTION.md), [DESIGN-ASSETS.md](DESIGN-ASSETS.md).

### Known weaknesses carried forward

1. **Never used on a real project.** Every claim about whether this helps is untested.
2. **Anchored scoring is better, not proven.** Requiring a cited comparison should stop score inflation; whether it does is unmeasured.
3. **Four budget rows are unverified**, including both prices the recommended ₹2,649 configuration depends on.
4. **The Low-confidence router path is still untested** — the v0.1.0 dry runs were all clear cases.
5. **No mode covers installations or physical computing.** `game-experiment` is the least-wrong fit and its defaults (DOM-first, desktop, keyboard) are all wrong for one.

---

## 0.1.0 — 2026-08-21

Initial system. 71 files. Validated by dry run only.

Superseded the same day, after an audit found: **49 verbatim duplicated sentences** across files, 2 orphan files, 8,871 words with no consumer, and a self-scored quality mechanism with no anchor.

**The lesson worth keeping:** building to a file-count specification produced scaffolding that served the specification rather than the user. The audit's most useful question was not "is this correct?" but **"who reads this, and what decision does it change?"** Eleven files could not answer it.

---

## Validation status

**READY FOR V1 VALIDATION** — not v1.0.0.

Three real-world tests are defined in [tests/validation-protocol.md](tests/validation-protocol.md).
**None have been run.** Builder OS does not earn the v1.0.0 tag until at least Test A and Test B
are complete, because nothing before that point is evidence about real work.

Before day 1: `corepack enable` (pnpm is not installed) · confirm the Cursor India and ChatGPT
prices **at checkout** and date them in [BUDGET-POLICY.md](BUDGET-POLICY.md) · record your baseline
honestly — how long did your last comparable project take, and what would you have shipped?

---

## The change process

**A retrospective proposes. Tanishk approves. Only then does a file change.** Nothing else may
mutate Builder OS — not a build session, not a review, not a good idea mid-project.

| Step | Who | Output |
|---|---|---|
| Observation | Anyone, during work | A line in the project's `RETROSPECTIVE.md` |
| Lesson candidate | Strategist at S6 | Passes all four qualification tests, or is dropped |
| Change proposal | Strategist | The block in [templates/RETROSPECTIVE.md](templates/RETROSPECTIVE.md) 4b |
| **Approval** | **Tanishk. Always.** | approve · defer · reject |
| Change | Strategist | One file, exactly as the proposal quoted it |
| **Regression** | Deterministic | `python scripts/check.py` · plus [tests/router-cases.md](tests/router-cases.md) if routing was touched |
| Log | Strategist | An entry below, naming the **cause** |

**If a regression check fails, revert.** The system is text; rollback is free and should be used
rather than debated.

**Rejected and deferred proposals are not logged here** — they stay in the project's retrospective.
This file records what changed, not what was considered.

### Additions require evidence

After V1 the burden inverts: the default answer to any addition is no.

| To add | Evidence required |
|---|---|
| A new **mode** | Multiple real projects routed badly, *and* a genuinely distinct workflow — different documents, questions, gates, QA. Not just different subject matter. |
| A new **skill** | A method you could not derive from an existing policy, needed on two projects. A checklist belongs in a policy. |
| A new **policy** | The same decision made badly twice for lack of a stated rule. |
| A new **script** | The manual version ran three times and caught something at least once. |
| A new **role** | **Unique authority** — something it can approve or reject that no existing role can. A review lens is not a role. |
| A new **document** | A named consumer, a stage, and a decision it changes. If it cannot answer all three, it is a section of an existing file. |

---

## How to log a change

```markdown
## 0.x.y — YYYY-MM-DD

### Changed
- <what> in <file> — because <what happened, on which project>
```

Log removals too — a deleted rule is as informative as an added one. If a retrospective changed nothing, write that with the reason: a run of "nothing changed" entries means either the system is stable or the retrospectives are not honest, and it is worth knowing which.
