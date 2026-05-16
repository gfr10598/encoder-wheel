#!/usr/bin/env python3
"""OCP CAD Viewer preview runner.

Run this file (or use the OCP right-click "Preview in OCP" / "Toggle visually
watching the CAD model") to build the half-ring cover and push it into the
OCP CAD Viewer panel via ocp_vscode.show().
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import traceback


def _alert(title: str, message: str) -> None:
    """Show a native macOS alert dialog. No-ops silently on non-macOS."""
    if sys.platform != "darwin":
        return
    safe = message[:400].replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e", f'display alert "{title}" message "{safe}"'],
        check=False,
        capture_output=True,
    )


try:
    # Ensure repo root is on sys.path so scripts.* imports resolve
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT))

    # Prevent parallel builds if watch mode fires multiple saves quickly.
    import fcntl

    _lock_file = open(ROOT / ".ocp_preview.lock", "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("ocp_preview_runner: another build is already running, skipping.")
        sys.exit(0)

    from scripts.cad.generate_half_ring_docs import design_data
    from scripts.cad.generate_half_ring_3d import make_cover
    from ocp_vscode import show, set_port

    # OCP CAD Viewer uses port 3939 by default
    set_port(3939)

    data = design_data()
    cover = make_cover(data)

    show(cover, names=["half_ring_cover"])

except Exception as e:
    tb = traceback.format_exc()
    print(tb)
    _alert("ocp_preview_runner.py failed", str(e))
    raise
