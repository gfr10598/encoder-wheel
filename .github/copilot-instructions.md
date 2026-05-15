# Copilot Instructions

Use [`/AGENTS.md`](../AGENTS.md) as the primary project memory file.

Key long-term guidance:

- this is a standard-library-only Python generator repo (CAD in `scripts/cad/`, magnetic analysis in `scripts/magnetic/`)
- `scripts/common.py` is the shared geometry core
- prefer script-generated SVG/documentation assets over hand-edited drawings
- validate changes with: `python -m py_compile scripts/*.py scripts/cad/*.py scripts/magnetic/*.py`
- the 10 in half-ring-over-magnets concept is documented in `AGENTS.md`
