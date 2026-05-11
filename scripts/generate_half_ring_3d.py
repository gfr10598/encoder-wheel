#!/usr/bin/env python3
"""
Generate a build123d 3D model of the 10 in half-ring magnet cover.

The half ring snaps over a 1/8 in steel backing half ring and its 45-magnet
array (90 magnets total, 20×5×2 mm each).

Coordinate convention
---------------------
  XY plane: the ring plane (rotation axis = Z)
  Z = 0   : base outer face (print-bed face for FDM)
  Z > 0   : into the printed base skin
  Z = bt  : base inner face / start of capture walls
  Z = bt + wall_h : open (snap) end of capture walls

The part is designed to print flat on Z=0 with walls pointing upward.
When installed, the Z=0 face is away from the magnets; the walls reach
down and snap over the steel ring.

Usage
-----
    conda run -n base python scripts/generate_half_ring_3d.py [options]

Options
-------
  --output-dir DIR   Directory for output files (default: examples/)
  --step             Also export a STEP file (default: STL only)
  --no-stl           Skip STL export
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from generate_half_ring_docs import INCH, design_data

from build123d import (
    Align,
    BuildPart,
    BuildSketch,
    Circle,
    Mode,
    Plane,
    Rectangle,
    extrude,
    export_stl,
    export_step,
)


def _semi_annulus(r_inner: float, r_outer: float) -> None:
    """Add a Y≥0 semi-annular region to the active BuildSketch context.

    Draws a full annulus then subtracts the Y<0 half with a rectangle
    whose top edge sits at y=0 so the result is the upper semicircle only.
    """
    clip_w = (r_outer + 2) * 2
    Circle(r_outer)
    Circle(r_inner, mode=Mode.SUBTRACT)
    Rectangle(clip_w, r_outer * 2, align=(Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)


def build_half_ring(data: dict):
    """Build and return the half-ring cover as a build123d Part.

    Parameters
    ----------
    data : dict
        Design parameters from :func:`generate_half_ring_docs.design_data`.

    Returns
    -------
    build123d Part
    """
    cir  = data["cover_inner_radius"]   # cover inner radius  (mm)
    cor  = data["cover_outer_radius"]   # cover outer radius  (mm)
    sir  = data["steel_inner_radius"]   # steel ring inner radius (mm)
    sor  = data["steel_outer_radius"]   # steel ring outer radius (mm)
    bt   = data["base_thickness"]       # base skin thickness: 1.0 mm
    st   = data["steel_thickness"]      # steel ring thickness: 3.175 mm (1/8 in)
    swe  = data["steel_wall_extra"]     # extra wall height above steel: 1.0 mm
    snap = data["snap_overhang"]        # snap overhang: 0.2 mm

    wall_h = st + swe                   # total capture-wall height: 4.175 mm

    with BuildPart() as part:

        # ── Base skin (full semi-annulus, covers inner and outer walls) ──
        with BuildSketch(Plane.XY):
            _semi_annulus(cir, cor)
        extrude(amount=bt)

        # ── Inner capture wall: cover inner edge → steel inner edge ──
        # Thickness = cir to sir = 1/8 in (3.175 mm)
        with BuildSketch(Plane(origin=(0, 0, bt))):
            _semi_annulus(cir, sir)
        extrude(amount=wall_h)

        # ── Outer capture wall: steel outer edge → cover outer edge ──
        # Thickness = sor to cor = 1/8 in (3.175 mm)
        with BuildSketch(Plane(origin=(0, 0, bt))):
            _semi_annulus(sor, cor)
        extrude(amount=wall_h)

        # ── Inner snap overhang ───────────────────────────────────────
        # Protrudes inward (toward axis) from the cavity-facing face of the
        # inner wall at the free (open) end.  Grips the inner edge of the
        # steel ring from below when installed.
        with BuildSketch(Plane(origin=(0, 0, bt + wall_h))):
            _semi_annulus(cir - snap, cir)
        extrude(amount=snap)

        # ── Outer snap overhang ───────────────────────────────────────
        # Protrudes outward (away from axis) from the cavity-facing face of
        # the outer wall at the free (open) end.
        with BuildSketch(Plane(origin=(0, 0, bt + wall_h))):
            _semi_annulus(cor, cor + snap)
        extrude(amount=snap)

    return part.part


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate 10 in half-ring cover 3D model using build123d"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: examples/)",
    )
    parser.add_argument(
        "--step",
        action="store_true",
        default=False,
        help="Also export a STEP file",
    )
    parser.add_argument(
        "--no-stl",
        action="store_true",
        default=False,
        help="Skip STL export",
    )
    args = parser.parse_args()

    if args.output_dir is None:
        repo_root = Path(__file__).resolve().parents[1]
        output_dir = repo_root / "examples"
    else:
        output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = design_data()
    cid = 2.0 * data["cover_inner_radius"] / INCH
    cod = 2.0 * data["cover_outer_radius"] / INCH
    print(
        f"Building half-ring cover: ID={cid:.3f} in ({2*data['cover_inner_radius']:.2f} mm),"
        f" OD={cod:.3f} in ({2*data['cover_outer_radius']:.2f} mm)"
    )
    print(
        f"  walls: {data['cover_wall']:.3f} mm (1/8 in) each side,"
        f" depth: {data['steel_thickness'] + data['steel_wall_extra']:.3f} mm,"
        f" snap: {data['snap_overhang']:.1f} mm"
    )

    part = build_half_ring(data)

    if not args.no_stl:
        stl_path = output_dir / "half_ring_cover.stl"
        export_stl(part, str(stl_path))
        print(f"  \u2192 {stl_path}")

    if args.step:
        step_path = output_dir / "half_ring_cover.step"
        export_step(part, str(step_path))
        print(f"  \u2192 {step_path}")


if __name__ == "__main__":
    main()
