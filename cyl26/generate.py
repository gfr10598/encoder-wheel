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

import argparse
import time
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
    export_step,
    extrude,
    fillet,
    offset,
)

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


def magnet_pocket(cfg: dict, angle: float = 0.0):
    """Magnet pocket at the given angle (degrees).

    The pocket is offset by cl/2 and its centre shifted outward by cl/2, so
    that the pocket inner face, magnet inner face, and shaft surface all
    coincide.  Clearance on the 5 remaining faces is cl/2 (tangential &
    axial) and cl on the outer radial face.
    """
    mc = cfg["magnet"]
    cyl = cfg["cylinder"]
    cl = mc["pocket_clearance_mm"]
    shaft_r = cfg["shaft"]["outer_radius_mm"]
    pocket_r = shaft_r + mc["radial_mm"] / 2 + cl / 2
    z_center = cyl["length_mm"] / 2

    positioned = magnet_body(cfg).moved(Location((pocket_r, 0, z_center)))
    with BuildPart() as bp:
        add(positioned)
        offset(amount=cl / 2)
    return bp.part.moved(Rotation(0, 0, angle))


def snap_opening(cfg: dict, angle: float = 0.0):
    """Snap-in opening through the bore wall at the given angle (degrees).

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

    return (
        Box(
            mc["radial_mm"],
            mc["tangential_mm"] - 2 * lip,
            mc["axial_mm"] - 2 * lip,
        )
        .moved(Location((snap_r, 0, z_center)))
        .moved(Rotation(0, 0, angle))
    )


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


def _build_model(cfg: dict):
    """Return (sleeve, magnet, angles) — magnet is reference-only (viewer)."""
    angles = magnet_angles_deg(cfg)
    pockets = [magnet_pocket(cfg, a) for a in angles]
    snaps = [snap_opening(cfg, a) for a in angles]
    sleeve = make_sleeve(cfg, pockets=pockets + snaps)
    shaft_r = cfg["shaft"]["outer_radius_mm"]
    magnet_r = shaft_r + cfg["magnet"]["radial_mm"] / 2
    z_mid = cfg["cylinder"]["length_mm"] / 2
    magnet = (
        magnet_body(cfg)
        .moved(Location((magnet_r, 0, z_mid)))
        .moved(Rotation(0, 0, angles[0]))
    )
    return sleeve, magnet, angles


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate PETG sleeve model.")
    p.add_argument(
        "--export",
        action="store_true",
        help="Write sleeve.step and sleeve.stl to the cyl26/ directory instead of opening the OCP viewer.",
    )
    p.add_argument(
        "--out-dir",
        default=str(Path(__file__).parent),
        help="Output directory for exported files (default: cyl26/).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    cfg = load_config()

    t0 = time.monotonic()
    sleeve, magnet, angles = _build_model(cfg)
    print(f"build   {time.monotonic() - t0:.1f}s")

    if args.export:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        step_path = out / "sleeve.step"
        t1 = time.monotonic()
        export_step(sleeve, str(step_path))
        print(f"export  {time.monotonic() - t1:.1f}s  → {step_path}")
    else:
        from ocp_vscode import set_port, show  # type: ignore

        set_port(3939)
        show(
            sleeve,
            magnet,
            names=["sleeve", "magnet"],
            colors=[None, "blue"],
            alphas=[0.9, 1.0],
            render_edges=True,
        )
else:
    # Allow `from cyl26.generate import …` without side-effects.
    pass
