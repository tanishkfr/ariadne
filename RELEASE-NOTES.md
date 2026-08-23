# Builder OS 1.5.3

Builder OS 1.5.3 prepares the installed product for stranger-friendly use while
preserving the V1.5 creative workflow, V1.5.1 optional Claude boundary and
V1.5.2 social capability.

## Highlights

- Fresh installs register `$builderos` in Codex's documented user skill path.
- An optional, managed general Codex baseline can be installed without
  overwriting existing user or project instructions.
- Update, rollback, doctor and uninstall understand that optional baseline and
  preserve it if the user edits it.
- Short Windows file-sharing violations no longer make atomic state writes
  fail nondeterministically.
- Release output includes one aggregate checksum inventory, versioned release
  notes and source-commit provenance.
- Runtime and wheel distributions carry the human-approved Apache-2.0 licence.

## Compatibility

- Python 3.8 or newer.
- Windows is directly exercised.
- macOS and Linux paths are simulated; native installation remains unverified.
- Codex is the default. Claude remains optional and is not required to install.
- Existing project-state schema 1 remains supported; no project migration is
  introduced.

## Evidence limits

Packaging and isolated lifecycle tests do not prove fresh external Codex skill
discovery, native macOS/Linux behaviour, live Claude execution or public GitHub
download availability. The release has not been published.
