# TROUBLESHOOTING

Start with:

```bash
python -m ariadne doctor
```

The command checks Python compatibility, the active installation, runtime file
hashes, managed skill parity, installation-history availability, Codex detection, optional Claude detection,
optional Codex baseline state and project-state compatibility. Missing provider
commands are warnings because desktop applications may still be installed.

## Common results

### `pip show ariadne` describes a GraphQL library

That is the unrelated Ariadne GraphQL package. Do not install this product into
the same Python environment because the distribution and import names collide.
Use a separate interpreter or virtual environment; neither package should
replace the other.

### Ariadne is not installed

Run `python -m ariadne install`.

### Runtime or skill is damaged

Run `python -m ariadne install` again. It repairs only managed files. If an
unknown file is present in the skill directory, move it elsewhere first;
Ariadne will not delete it.

### An update cannot connect

The active installation remains available. Check network access and retry later.
Normal project work does not need the update service unless the current stage
requires online research or an external provider.

### A project is incompatible

Do not edit its run metadata. Keep the current runtime or use
`python -m ariadne rollback`; a future migration must be explicit and
recorded.

### Codex does not show `$ariadne`

Run doctor, then `python -m ariadne install` to repair registration. Restart
Codex so it reloads installed skills.

### The optional Codex baseline was skipped

Ariadne found an existing `AGENTS.md` or `AGENTS.override.md` and preserved
it. This does not block `$ariadne`. Keep your existing instructions, or merge
the published generic defaults yourself; Ariadne will not claim ownership of
that manual merge.

### The optional Codex baseline was edited

Ariadne preserves edited instructions during update and uninstall. Run
`python -m ariadne codex-baseline status` to confirm the state. Use `remove`
to remove only Ariadne ownership; the edited instruction file remains.

### Claude is unavailable or does not show `$ariadne`

Claude is optional. Confirm its CLI is already installed and available on
`PATH`, then run `python -m ariadne enable-claude`. If detection still fails,
continue with Codex; no project repair or migration is required. Use
`disable-claude` to remove a damaged optional entry before rollback.

### I need the actual paths

For diagnostics only:

```bash
python -m ariadne paths
```

Never move an active version directory manually. Use update, rollback or
uninstall so the runtime and skill remain paired.

Next: copy the complete `ariadne doctor` output into a support report.
