# UPDATE, ROLLBACK AND UNINSTALL

## Update

```bash
python -m builderos update
```

Update downloads the HTTPS release description and checksum-bound runtime,
verifies every canonical file, installs a new immutable version directory, then
atomically moves the active pointer and managed skill. It never rewrites a
project document.

If an update fails before activation, the prior runtime remains current. After
a successful update, the command names the available rollback version.

## Roll back

```bash
python -m builderos rollback
python -m builderos doctor
```

Rollback activates the previous verified runtime and matching skill. Projects
and evidence remain unchanged.

## Repair

Running the installer again is safe:

```bash
python -m builderos install
```

It verifies the active runtime, repairs managed skill drift, and refuses to
overwrite unmanaged or user-added skill files.

## Uninstall

```bash
python -m builderos uninstall
python -m pip uninstall builder-os
```

The first command removes the user-local runtime and its managed skill while
preserving every project and project history. The second removes the small
Python launcher; keeping the steps separate avoids a process trying to uninstall
itself.

Next: use [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if a health check fails.
