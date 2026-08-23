# Releasing Ariadne

This repository builds a deterministic runtime archive and launcher wheel from
an explicit source allowlist.

```bash
python -m compileall -q src scripts build_backend
python scripts/build-release.py --output dist
```

The generated runtime excludes test evidence, maintainer notes, credentials and
machine-specific paths. Release files include source-commit provenance and
SHA-256 checksums. Tagging and GitHub publication remain explicit human actions.
