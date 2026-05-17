#!/usr/bin/env bash
# Generate cyl26/sleeve.step for import into Bambu Studio (or any STEP-capable slicer).
set -euo pipefail
cd "$(dirname "$0")"
.venv/bin/python cyl26/generate.py --export
