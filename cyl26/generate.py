#!/usr/bin/env python3
"""
Cylindrical ring 3D model — PETG sleeve that mounts on existing 4-in cast iron tube.

Geometry (from config.json)
---------------------------
  Cast iron shaft (reference): OD = 101.6 mm (r = 50.8 mm)  — not printed
  PETG sleeve               : bore fits over tube OD with clearance
  Magnets (reference)       : 26 × 20×10×5 mm, radially on outer surface

Coordinate system
-----------------
  Z axis = shaft/sleeve axis, Z=0 at bottom face of sleeve.
  Magnet #0 at θ=0 (along +X).

Usage
-----
  .venv/bin/python cyl26/generate.py
"""

from __future__ import annotations

import json
from pathlib import Path

from build123d import (
    BuildPart,
    BuildSketch,
    Circle,
    Mode,
    Plane,
    extrude,
)
from ocp_vscode import set_port, show  # type: ignore

CONFIG = Path(__file__).parent / "config.json"


def load_config() -> dict:
    with open(CONFIG) as f:
        return json.load(f)


def make_shaft(cfg: dict):
    """Reference body: existing cast iron shaft — shown at low opacity only."""
    r = cfg["shaft_outer_radius_mm"]
    length = cfg["cylinder_length_mm"]
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            Circle(r)
        extrude(amount=length)
    return p.part


def make_petg_sleeve(cfg: dict):
    """Blank PETG cylinder that fits over the cast iron shaft."""
    bore_r = cfg["shaft_outer_radius_mm"] + cfg["cylinder_bore_clearance_mm"]
    outer_r = bore_r + cfg["cylinder_wall_mm"]
    length = cfg["cylinder_length_mm"]
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            Circle(outer_r)
            Circle(bore_r, mode=Mode.SUBTRACT)
        extrude(amount=length)
    return p.part


# ── entry point ──────────────────────────────────────────────────────────────

cfg = load_config()
shaft = make_shaft(cfg)
sleeve = make_petg_sleeve(cfg)

set_port(3939)
show(
    shaft,
    sleeve,
    names=["shaft", "petg_sleeve"],
    colors=["black", None],
    alphas=[0.35, 1.0],
    render_edges=False,  # hides OCCT seam lines on closed cylinders
)
