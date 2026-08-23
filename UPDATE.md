# UPDATE, ROLLBACK AND UNINSTALL

## Update

```bash
python -m builderos update
```

Update downloads the HTTPS release description and checksum-bound runtime,
verifies every canonical file, installs a new immutable version directory, then
atomically moves the active pointer and managed skill. It never rewrites a
project document.

If the optional Codex baseline is installed and unchanged, update refreshes it
from the new verified runtime. If it was edited, Builder OS preserves it and
reports that it could not safely update the managed copy.

If an update fails before activation, the prior runtime remains current. After
a successful update, the command names the available rollback version.

## Roll back

If the optional Claude reasoner entry is enabled, remove it first:

```bash
python -m builderos disable-claude
```

```bash
python -m builderos rollback
python -m builderos doctor
```

Rollback activates the previous verified runtime and matching skill. Projects
and evidence remain unchanged. An unchanged managed Codex baseline follows the
rollback version; edited instructions remain untouched.

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
preserving every project and project history. It also removes an unchanged
Builder OS-managed Codex baseline. An edited baseline and all unrelated Codex
instructions are preserved. The second command removes the small Python
launcher; keeping the steps separate avoids a process trying to uninstall
itself.

Next: use [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if a health check fails.
