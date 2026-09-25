# AR-204 — Harness Map

What Ariadne actually sends, in what order, with what it costs.

Everything below was read from the running runtime and from packets the transport
produced in the benchmark sandbox; none of it is inferred from templates. Where a
figure is quoted, the file that measured it is named.

## 1. The request is the packet

Ariadne does not assemble a provider API call itself. The runtime prepares a
stage packet, and the packet **is** the request: an operator hands it to a Codex
session, an implementation worker or a reviewer. That makes the packet the unit
the harness map has to describe.

```text
runtime train
  ariadne.py prepare-next
      -> transport prepare()          chooses stage, sources, worker contract
      -> build_packet()               renders packet.txt
      -> manifest.json                records source hashes, omissions, worker block
      -> engine records               execution, context decision, events
```

`scripts/prepare-stage.py` is the only assembler. `build_packet` emits, in order:

1. the packet title line, packet id, provider and the `PREPARED ONLY` status;
2. the transport notice;
3. the Ariadne source commit and the parent packet, or the independence boundary
   at S5;
4. the S4B return target, the worker task contract and any repair context;
5. the declared conditional omissions;
6. the current stage prompt block, wrapped in `===== BEGIN … END =====`;
7. every delivered source, each in its own wrapped section carrying its label,
   path and two hashes.

Section boundaries are machine-readable, which is what lets
`ariadne_engine.harness` reconstruct the structure from a packet that already
exists instead of re-deriving it from the compiler's rules.

## 2. What the renderer reports

`harness.packet_map(text)` returns one row per section (the scaffolding as row
`-1`), each with:

| Field | Meaning |
| --- | --- |
| `bucket` | one of the fifteen AR-204 source buckets |
| `origin` | engine, policy, project, task, retrieved or unknown |
| `bytes`, `digest` | measured locally, always available |
| `stability`, `stability_basis` | reusable prefix or per-request value, with the reason |
| `volatile` | which volatile kinds the bounded scan found |
| `scan` | scanned versus total bytes, so a bounded scan is never read as complete |
| `cacheable`, `start_line`, `end_line` | structural facts |

The render is redacted before it is reported, and it is never consumed to build a
request: a defect in the inspector cannot change what a worker receives.

## 3. Message roles and tool declarations

The packet is one text document, so the renderer assigns the roles a provider
adapter would use: the preamble, the stage prompt block and the canonical policy
documents are `system`; project facts, design context, task content and evidence
are `user`. The mapping is in `harness.packet_render`.

Ariadne has no function-schema catalogue. What a stage can do arrives as
*declarations*: skills, canonical policies and capability registries inside the
packet, plus the engine capability families a route can select. `tooling` models
those as capability packs and measures their real file sizes, which is why the
tool-schema section of this milestone talks about packs rather than JSON schemas.

## 4. What is not re-sent

Every stage starts from a fresh bounded packet. A worker at S4B never receives the
S3 conversation, and the S5 reviewer receives the isolated pair and nothing else —
the transport refuses the forbidden inputs rather than trimming them. There is no
growing chat history to compact at the transport level; what can grow without
bound is a *worker transcript* and the engine's own record collections.

AR-204 therefore treats history as two different things:

* **run state**: append-only collections (executions, failures, decisions,
  verifications, artifacts) with declared bounds, never summarised;
* **worker transcript**: an ordered entry list that `history` can measure and, if
  the operator enables it, compact with the full original archived first.

## 5. The execution tree

Engine execution roles map onto the task-tree nodes the economics layer reports:

```text
task
├── coordinator           reasoner execution
├── decision batch        one provider request per independent question set
├── worker                implementer execution
│   └── repair            a later implementer execution after a failure
├── validation            validator execution
└── review                reviewer execution
```

`economics.task_tree` builds that tree from execution records, and
`economics.task_cost` sums only measured usage across every node — including the
failed ones. A run with no provider calls reports `UNKNOWN` for every token field
and no monetary figure, which is the honest state of the current milestone.

## 6. Where the volatile values sit

The measured finding of this milestone is that the packet's reusable content is
*behind* per-request values: the packet id, provider line, source commit, parent
packet and baseline head all appear before the stage prompt block. The transport
order is kept, because re-ordering what a worker reads is a behaviour change; what
AR-204 adds is the measurement and a stable-first plan any adapter can use.

```text
current packet                     stable-first plan
--------------------------         --------------------------
packet id        volatile          stable tool/capability declarations
provider         volatile          stable engine and policy context
source commit    volatile          ---- cache boundary ----
parent packet    volatile          project and session setup
worker contract  volatile          ---- cache boundary ----
prompt block     stable            volatile task, history, evidence
sources          stable
```

The rendered measurement is in `docs/v2/AR-204/measurements/ar-204-measurement-summary.json`
and is discussed in [05-CACHE-ARCHITECTURE.md](05-CACHE-ARCHITECTURE.md).

## 7. Read surfaces

| Surface | Command or function |
| --- | --- |
| Packet render, redacted | `ariadne.py request-map --packet <path>` |
| Source buckets and prefix | `harness.packet_map`, `harness.render_request` |
| Task tree and cost | `ariadne.py economics --task-id <id>` |
| Tool packs | `ariadne.py tool-packs --stage S4B` |
| Efficiency flags | `ariadne.py economics --json` |

## 8. What this map establishes

* The request is one assembled artifact, so request economics is packet economics.
* Section boundaries are recoverable from a produced packet, so the inspector
  measures reality rather than replicating the compiler.
* Volatile-first ordering is a measured fact, and the stable-first plan is
  available without changing what a worker reads today.
* Every stage is isolated, which is why AR-204's history work targets transcripts
  and record collections rather than a shared stage conversation.
