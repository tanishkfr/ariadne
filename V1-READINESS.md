# BUILDER OS V1 READINESS

**Assessment date:** 2026-08-23

**Hardening baseline:** `06d290655cd5e0e575b59fc0354591a94260d2bc`

**Rollback checkpoints:**

- `1b41c8e` — Test B closure evidence
- `fd3f139` — runtime orchestration and return contract
- `4fabc39` — recovery, discovery, and automatic progression

## V1 STATUS

**READY**

Builder OS now has a calm Codex entry, durable project/run discovery, automatic
canonical packet preparation, source and parent provenance, provider-aware
implementation routing, structured implementation return, isolated independent
review, review ingestion, recovery without evidence overwrite, and a readable
operations log. The user directs the project and grants meaningful gates; they
do not need to know stage IDs, prompts, manifests, hashes, parent paths, or
transcript locations.

READY does not mean every external provider behaviour was observed. Test B
proved the Cursor/Grok handoff could be consumed and implementation could begin,
then ended at a provider quota boundary. Live provider return remains externally
unverified; its contract and continuation path are structurally verified and
negative-tested, which is an accepted V1 evidence limitation rather than a
fabricated pass.

## OPERATOR EXPERIENCE

The normal path is:

1. Open a clean Codex task, invoke `$builderos`, and describe the project.
2. Builder OS starts or discovers the run, performs routing, intake, research,
   and direction work, and records evidence.
3. The human approves or rejects the creative direction at G1.
4. Builder OS writes the rich implementation handoff, reads its routing record,
   and checks observable provider availability/quota.
5. If an external builder is appropriate, the human performs one unavoidable
   action: open it at the project and paste the one verified packet.
6. Builder OS ingests the marked implementation return, verifies or routes
   follow-up QA, and creates an isolated review packet.
7. Builder OS preserves and applies the marked independent judgement without
   rewriting it, then presents G3. Shipping remains G4.

The low-level packet commands remain available for recovery, not routine use.

## IMPLEMENTED CAPABILITIES

| Capability | Owner | V1 behaviour | Evidence |
|---|---|---|---|
| Entry and resume | repository and managed personal `builderos` skill | Starts from ordinary language or discovers one matching durable run | skill contract tests; managed install verification |
| Orchestration | `scripts/builderos.py` | Infers the next valid boundary; explicit stage is an assertion, not an override | full synthetic S1-to-S5 progression; gate-bypass negative test |
| Canonical delivery | `scripts/prepare-stage.py` | Builds exact stage packets with source/parent hashes and isolation | packet self-test; repository checks |
| Evidence | controller plus packet manifests | Preserves transcripts when available; accepts structural same-session evidence without claiming a transcript | stale-output and canonical-drift controls |
| Provider routing | `MODEL-ROUTING.md`, `HANDOFF.md`, controller | Reads capability/provider/model/effort/workload/split; checks runtime availability/quota | verified, assumed, human-check, and blocked controls |
| External handoff | canonical S4 prompt and packet | Delivers design, runtime state, QA policy/template, and return contract | parity checks and Test B consumption |
| Return continuity | `templates/RETURN-HANDOFF.md`, controller | Validates complete/partial/blocked returns; complete may reach S5, partial creates a non-overwriting S4B retry | positive, malformed, partial, and retry controls |
| Independent review | S5 packet and controller | Delivers only target/intent/criteria/accepted patterns/rubric; preserves raw response and updates only QA judgement | isolation, placeholder, independence, marker, duplicate-ingestion controls |
| Operations history | per-run `OPERATIONS.md` | Records actions, reasons, files, evidence class, failures, repairs, and next action | full dry-run log integrity check |

## FRICTION REMOVED

- No manual prompt or template hunting.
- No manual packet concatenation or stale-source comparison.
- No manual parent/continuation IDs or transcript destinations.
- No manual re-entry of implementation-routing decisions already in `HANDOFF.md`.
- No opening a large external task before observable quota/availability preflight.
- No conversation-history dependency when implementation returns.
- No manual replacement or paraphrasing of the independent QA judgement.
- No project restart after a partial implementation; retries preserve the parent
  and earlier evidence.
- No silent choice between two histories claiming the same project.

## SKILLS

The four canonical method skills remain focused on intake, reference analysis,
design direction, and component research. Their policy did not need redesign.
The new repo-scoped `builderos` skill is an orchestration entry, not another
policy owner: it locates this repository and delegates routing, stage policy,
packet transport, and gates to their canonical owners.

The managed personal installation is verified against the repository copy and
refuses to overwrite an unmanaged skill. Skill metadata and trigger drift have
positive and negative controls.

## VALIDATION

- `python -m py_compile` for every changed Python file: PASS.
- `python scripts/check.py`: PASS; links, required files, ownership,
  delivery, packet, runtime, stage-chain, router, and duplicate guards green.
- `python scripts/check.py --self-test`: PASS; every integrated negative suite
  and its positive controls green.
- `python scripts/prepare-stage.py --self-test`: PASS, 24/24.
- `python scripts/builderos.py --self-test`: PASS, including full S1-to-S5
  progression, partial retry, and review ingestion.
- `python scripts/install-builderos-skill.py --self-test`: PASS, 5/5.
- `python scripts/validate.py --self-test`: PASS, 29/29 guards fail on their
  broken fixtures.
- Managed personal skill `install` and `verify`: PASS.
- `git diff --check`: PASS.

The generic skill-authoring helper could not execute because its Python runtime
does not include PyYAML. No package was installed to mask that environment fact;
the repository instead validates the skill frontmatter, UI metadata, trigger
contract, installation pointer, source parity, and drift with deterministic
positive and negative controls.

## PROVIDERS

**Codex:** entry skill installed and verified on this machine. The controller
and packet chain are behaviourally exercised in this task and structurally
covered in self-tests.

**Cursor/Grok:** the Test B handoff was consumed successfully and implementation
began. A quota limit stopped the live build before full QA and return. Current
S4B packet generation, provider labelling, return ingestion, partial retry, and
S5 isolation are structurally verified. A live complete return remains
externally unverified.

**Provider neutrality:** routing remains capability-first (`R1`-`R6`), canonical
handoffs are plain Markdown, and provider mechanics stay in adapters/transport.
Changing the provider does not change the project thesis or gate semantics.

## EVIDENCE CLASSIFICATION

### Verified

- Repository contracts, links, router cases, frozen gate/routing ownership.
- Managed skill installation and repository parity.
- Run discovery, ambiguity refusal, automatic progression, and recovery.
- Packet source/parent provenance and stale/damaged packet failure.
- Provider-preflight decision states.
- Structured return and independent-review ingestion.
- S5 context isolation.
- Test B handoff consumption and implementation start.

### Reasonably assumed

- A supported external implementation provider can complete a well-specified
  S4B packet when sufficient usage is available; Test B reached implementation
  before quota exhaustion.
- A fresh Codex task will discover the installed skill through the documented
  repository/user skill mechanism; installation and metadata are verified, but
  this hardening task did not create a second live Codex task merely to observe
  discovery UI.

### Externally unverified

- One complete live Cursor/Grok implementation-return cycle.
- Production deployment and rollback; neither was attempted.
- Provider-neutral live execution with a third implementation provider.
- Test C's multi-week content-learning loop.

### Blocked

None for repository V1 readiness. External implementation still requires the
human to operate the selected signed-in provider, and external release actions
remain deliberately gated.

## HUMAN DECISIONS REMAINING

- G1 creative direction and any restart that changes it.
- G2 dependency approval.
- Material scope/design trade-offs and waivers.
- The unavoidable signed-in external provider action when selected.
- G3 acceptance of build/review evidence.
- G4 ship and G5 publish authority.

These are product boundaries, not operator ceremony.

## CURSOR READY FOR USE

The handoff is generated and verified automatically. The one manual action is
opening the signed-in provider at the project and pasting the packet. The
provider must return the marked implementation block. Builder OS handles its
storage, validation, retry lineage, and continuation.

## OPERATIONS LOGS

- Hardening run: [`operations/V1-PRODUCTIONIZATION.md`](operations/V1-PRODUCTIONIZATION.md)
- Each project: `<run-root>/OPERATIONS.md`, discoverable from the project with
  `builderos.py discover --project <project>` when debugging.

## PRODUCT NAME

**Recommendation: keep “Builder OS” for V1.** It is already embedded in evidence,
prompts, adapters, and operator language, and describes the product without
claiming autonomous creative authority. A mythological rename would create
migration and trademark work without improving the operator path. Revisit only
after repeated real use reveals a clearer identity; naming is not a V1 blocker.

## NEXT MANUAL SESSION

1. Open a clean Codex task in a fresh project and invoke `$builderos`.
2. Describe one real project normally and judge only the meaningful questions
   and G1 direction.
3. If Builder OS selects Cursor/Grok, confirm observable quota, paste the one
   generated packet, and return its marked handoff.
4. Continue through independent review and G3; do not deploy unless G4 is
   explicitly approved.
