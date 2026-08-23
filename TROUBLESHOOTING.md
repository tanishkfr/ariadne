# TROUBLESHOOTING

Start with:

```bash
python -m builderos doctor
```

The command checks Python compatibility, the active installation, runtime file
hashes, managed skill parity, Codex detection and optional project-state
compatibility. A missing Codex command is reported as a warning because the
desktop app may still be installed.

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

### I need the actual paths

For diagnostics only:

```bash
python -m builderos paths
```

Never move an active version directory manually. Use update, rollback or
uninstall so the runtime and skill remain paired.

Next: copy the complete `builderos doctor` output into a support report.
