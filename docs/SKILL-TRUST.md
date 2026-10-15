# External skill trust model

> Ariadne 2.3C. This document states what the external-skill boundary is, why it
> is shaped this way, and what it refuses. The implementation lives in
> [`ariadne_engine/external_skills.py`](../src/ariadne_engine/external_skills.py);
> the operator surface is `ariadne.py skills-discover | skills-approve |
> skills-install | skills-status`.

## Why this exists

Native Ariadne skills ship with the product and are reviewed with it, so loading
one is safe by construction. Anything from outside that boundary is untrusted
input until a human has looked at it. The point of the trust model is to make
reuse *possible* without letting a downloaded file become authority.

## The five rules

1. **Metadata before instructions.** `skills-discover` reads at most 16 KiB of
   each candidate's `SKILL.md` front matter (the Agent Skills format: `name`,
   `description`, optional `metadata`). The instruction body is not parsed until
   an approved skill is loaded for a task.
2. **Nothing is executed.** Discovery starts no process, runs no install script,
   and writes nothing. Installation is a *copy* of the skill directory into the
   run's managed store; a `install.py` inside a skill is copied like any file and
   never run.
3. **Untrusted until approved.** A candidate is `untrusted` by default. Approval
   (`skills-approve --identity <human>`) records one human identity bound to one
   skill id, one exact SHA-256 digest, and a scope of families. There is no
   anonymous approval and no wildcard. If the file changes afterwards, the
   approval is `stale` and the skill is unselectable until re-approved.
4. **No authority laundering.** The description is scanned at inspection and the
   full body again at load time for authority-minting language (granting
   approvals, disabling policy, minting verification, bypassing gates), for
   dangerous instructions (running installers, piping the network into a shell,
   reading credential files), and for credential-shaped content. Any hit refuses
   the skill at that step. Selection with an approved external still grants
   nothing: the entry carries a declared permission and the plan's authority is
   unchanged.
5. **No duplication of native functionality without a stated benefit.** An
   external skill that claims a native id is refused. A declared overlap with a
   native skill must carry a `benefit` or the candidate is rejected.

## What an evaluation record states

Before any approval, `skills-discover` prints (and `--json` returns) the full
evaluation for each candidate: identifier, version, publisher, licence, pinned
digest, required tools/capabilities, host compatibility, declared permission,
applicable families, overlap declarations, context cost in bytes, and every
trust problem found. A human approves from that record, not from a README.

## Selection order

1. Native Ariadne skills (always win an id collision).
2. Previously approved and installed external skills, digest-verified, whose
   declared families match the task — auto-selected because a human already
   approved them *for those families*.
3. Explicitly requested ids (`--approved-external` on the task commands must
   name a recorded approval; an unrecorded id is refused, not silently ignored).
4. Newly discovered candidates are only ever *suggested* (a briefing appears when
   the native selection recorded capability gaps); they are never selected and
   never installed automatically.

## Storage and inspection

- Approvals live in the run state (`external_skill_approvals`), like every other
  approval: inspectable, attributable, part of the project's history.
- Installs live under the run root's `external-skills/<id>/` with an
  `INSTALL.json` recording the digest of every file. `skills-status` shows each
  approval's current state (`approved`, `stale`, `rejected`, missing files) and
  `verify_install` re-hashes the store on every registry build.
- A skill that was approved and installed in one run is reusable in that run's
  later tasks. Projects are separate trust domains on purpose.

## What this deliberately is not

No marketplace, no hosted registry, no network fetching, no package manager, no
auto-update. Catalogues are directories the operator names explicitly.
