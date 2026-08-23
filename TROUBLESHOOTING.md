# TROUBLESHOOTING

Start with:

```bash
python -m builderos doctor
```

The command checks Python compatibility, the active installation, runtime file
hashes, managed skill parity, installation-history availability, Codex detection, optional Claude detection,
optional Codex baseline state and project-state compatibility. Missing provider
commands are warnings because desktop applications may still be installed.

## Common results

### Builder OS is not installed

Run `python -m builderos install`.

### Runtime or skill is damaged

Run `python -m builderos install` again. It repairs only managed files. If an
unknown file is present in the skill directory, move it elsewhere first; Builder
OS will not delete it.

### An update cannot connect

The active installation remains available. Check network access and retry later.
Normal project work does not need the update service unless the current stage
requires online research or an external provider.

### A project is incompatible

Do not edit its run metadata. Keep the current runtime or use
`python -m builderos rollback`; a future migration must be explicit and
recorded.

### Codex does not show `$builderos`

Run doctor, then `python -m builderos install` to repair registration. Restart
Codex so it reloads installed skills.

### The optional Codex baseline was skipped

Builder OS found an existing `AGENTS.md` or `AGENTS.override.md` and preserved
it. This does not block `$builderos`. Keep your existing instructions, or merge
the published generic defaults yourself; Builder OS will not claim ownership of
that manual merge.

### The optional Codex baseline was edited

Builder OS preserves edited instructions during update and uninstall. Run
`python -m builderos codex-baseline status` to confirm the state. Use `remove`
to remove only Builder OS ownership; the edited instruction file remains.

### Claude is unavailable or does not show `$builderos`

Claude is optional. Confirm its CLI is already installed and available on
`PATH`, then run `python -m builderos enable-claude`. If detection still fails,
continue with Codex; no project repair or migration is required. Use
`disable-claude` to remove a damaged optional entry before rollback.

### I need the actual paths

For diagnostics only:

```bash
python -m builderos paths
```

Never move an active version directory manually. Use update, rollback or
uninstall so the runtime and skill remain paired.

Next: copy the complete `builderos doctor` output into a support report.
