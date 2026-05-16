#!/usr/bin/env python3
"""
Cylindrical ring 3D model — PETG sleeve that mounts on existing 4-in cast iron tube.

Geometry (from config.yaml)
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

import math
from pathlib import Path

import yaml

from build123d import (
    Axis,
    Box,
    BuildLine,
    BuildPart,
    BuildSketch,
    Circle,
    Face,
    Location,
    Mode,
    Plane,
    Rotation,
    ThreePointArc,
    add,
    extrude,
    fillet,
    offset,
)
from ocp_vscode import set_port, show  # type: ignore

CONFIG = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG) as f:
        return yaml.safe_load(f)


def magnet_angles_deg(cfg: dict) -> list[float]:
    """Return center angles (degrees) for all magnets.

    The first magnet is offset by half the angular pitch so that no magnet
    straddles the split plane declared in cfg['split']['plane'].
    """
    n = cfg["magnet"]["count"]
    pitch = 360.0 / n
    first = pitch / 2.0  # half-pitch offset keeps gaps on both plane crossings
    return [first + i * pitch for i in range(n)]


def circle_wire(r: float):
    """Full circle wire of radius r in the XY plane (two semicircular arcs)."""
    with BuildLine() as bl:
        ThreePointArc((r, 0), (0, r), (-r, 0))
        ThreePointArc((-r, 0), (0, -r), (r, 0))
    return bl.wire()


def annulus_face(bore_r: float, outer_r: float) -> Face:
    """Full annular (washer) face in the XY plane."""
    return Face.make_from_wires(circle_wire(outer_r), [circle_wire(bore_r)])


def magnet_body(cfg: dict):
    """Magnet as a filleted box at the origin (no clearance, no placement offset)."""
    mc = cfg["magnet"]
    with BuildPart() as bp:
        Box(mc["radial_mm"], mc["tangential_mm"], mc["axial_mm"])
        # radially-aligned edges (Axis.X) get the larger rounding; others get smaller
        fillet(bp.edges().filter_by(Axis.X), mc["radial_rounding_mm"])
        fillet(
            bp.edges().filter_by(Axis.Y) + bp.edges().filter_by(Axis.Z),
            mc["other_rounding_mm"],
        )
    return bp.part


def magnet_pocket_at_zero(cfg: dict):
    """Single magnet pocket at θ=0.

    The pocket is offset by cl/2 and its centre shifted outward by cl/2, so
    that the pocket inner face, magnet inner face, and shaft surface all
    coincide.  Clearance on the 5 remaining faces is cl/2 (tangential &
    axial) and cl on the outer radial face.
    """
    mc = cfg["magnet"]
    cyl = cfg["cylinder"]
    cl = mc["pocket_clearance_mm"]
    shaft_r = cfg["shaft"]["outer_radius_mm"]
    # Pocket centre is cl/2 outward from the magnet centre so the inner faces align.
    pocket_r = shaft_r + mc["radial_mm"] / 2 + cl / 2
    z_center = cyl["length_mm"] / 2

    positioned = magnet_body(cfg).moved(Location((pocket_r, 0, z_center)))
    with BuildPart() as bp:
        add(positioned)
        offset(amount=cl / 2)
    return bp.part


def snap_opening_at_zero(cfg: dict):
    """Snap-in opening through the bore wall.

    A plain box 0.2 mm smaller than the magnet on the tangential and axial
    faces, centred 2 mm inward (toward axis).  This leaves a 0.2 mm lip
    around the bore opening so magnets snap in from the inside.
    """
    mc = cfg["magnet"]
    cyl = cfg["cylinder"]
    shaft_r = cfg["shaft"]["outer_radius_mm"]
    snap_r = shaft_r + mc["radial_mm"] / 2 - 2.0  # 2 mm inward from magnet centre
    z_center = cyl["length_mm"] / 2
    lip = mc["snap_lip_mm"]

    return Box(
        mc["radial_mm"],
        mc["tangential_mm"] - 2 * lip,
        mc["axial_mm"] - 2 * lip,
    ).moved(Location((snap_r, 0, z_center)))


def make_sleeve(cfg: dict, pockets=()):
    """Full PETG sleeve — split in slicer (e.g. Bambu Studio)."""
    bore_r = cfg["shaft"]["outer_radius_mm"] + cfg["cylinder"]["bore_clearance_mm"]
    outer_r = bore_r + cfg["cylinder"]["wall_mm"]
    length = cfg["cylinder"]["length_mm"]
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            Circle(outer_r)
            Circle(bore_r, mode=Mode.SUBTRACT)
        extrude(amount=length)
        for pocket in pockets:
            add(pocket, mode=Mode.SUBTRACT)
    return p.part


# ── entry point ──────────────────────────────────────────────────────────────

cfg = load_config()
pocket = magnet_pocket_at_zero(cfg)
snap = snap_opening_at_zero(cfg)
sleeve = make_sleeve(cfg, pockets=[pocket, snap])
magnet = magnet_body(cfg)
shaft_r = cfg["shaft"]["outer_radius_mm"]
magnet_r = shaft_r + cfg["magnet"]["radial_mm"] / 2
z_mid = cfg["cylinder"]["length_mm"] / 2
magnet = magnet.moved(Location((magnet_r, 0, z_mid)))
set_port(3939)
show(
    sleeve,
    magnet,
    names=["sleeve", "magnet"],
    colors=[None, "blue"],
    alphas=[0.9, 1.0],
    render_edges=True,
)
