#!/usr/bin/env python3
"""
Generate an SVG file for laser-cutting an encoder-wheel template.

The output is a 2-D flat template with:
  • An outer ring boundary (the disc edge)
  • Rectangular slots for the magnets
  • A center bore hole
  • (Optionally) a reference engraving circle at the inner radius

The slots use a kerf-compensation offset so the magnet fits snugly after
cutting.  Since the inner corners of adjacent slots are touching, the
inter-slot "spokes" taper to a point at the inner radius — the inner rim
is structurally detached from the outer ring.

Colour convention (common for laser-cutter software)
----------------------------------------------------
  Red (#FF0000)  — through-cuts
  Blue (#0000FF) — engraving / score lines

Usage
-----
    python scripts/generate_laser.py [options]

Options
-------
  --n-magnets N          Number of magnets (multiple of 12, default 12)
  --length L             Magnet radial length in mm (default 20)
  --width W              Magnet tangential width in mm (default 5)
  --thickness T          Magnet axial thickness mm — sets sheet thickness
                         used in on-screen notes only (default 2)
  --inner-radius R       Inner radius in mm (default = minimum possible)
  --margin M             Extra ring width outside magnet tips in mm (default 3)
  --kerf K               Laser kerf half-compensation in mm (default 0.1)
  --center-hole-radius R Radius of central shaft hole in mm (default 5)
  --no-center-hole       Omit the central hole
  --output FILE          Output SVG filename (default encoder_wheel_laser.svg)
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import encoder_geometry


# ---------------------------------------------------------------------------
# Tiny SVG helpers
# ---------------------------------------------------------------------------

def _pts_to_path(points, close=True) -> str:
    """Return an SVG path ``d`` attribute string from a list of (x, y) tuples."""
    parts = [f"M {points[0][0]:.4f},{points[0][1]:.4f}"]
    for x, y in points[1:]:
        parts.append(f"L {x:.4f},{y:.4f}")
    if close:
        parts.append("Z")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_laser_svg(
    n_magnets: int = 12,
    magnet_length: float = 20.0,
    magnet_width: float = 5.0,
    magnet_thickness: float = 2.0,
    inner_radius: float = None,
    margin: float = 3.0,
    kerf: float = 0.1,
    center_hole: bool = True,
    center_hole_radius: float = 5.0,
) -> str:
    """Generate the SVG content string.

    Parameters
    ----------
    n_magnets : int
        Number of magnets.
    magnet_length : float
        Radial length of each magnet (mm).
    magnet_width : float
        Tangential width of each magnet (mm).
    magnet_thickness : float
        Axial thickness of each magnet (mm) — used in the parameter note only.
    inner_radius : float, optional
        Inner radius (mm); defaults to minimum (inner corners touching).
    margin : float
        Extra ring width beyond the outer magnet tips (mm).
    kerf : float
        Kerf compensation: each slot is expanded by this amount on each side
        so that the magnet fits after the laser removes material.
    center_hole : bool
        Whether to cut a central shaft hole.
    center_hole_radius : float
        Radius of the central shaft hole (mm).

    Returns
    -------
    str
        SVG file content.
    """
    geo = encoder_geometry(
        n_magnets=n_magnets,
        magnet_length=magnet_length,
        magnet_width=magnet_width,
        magnet_thickness=magnet_thickness,
        inner_radius=inner_radius,
    )

    r_outer_ring = geo["outer_radius"] + margin

    # SVG viewport — add a small padding around the disc
    padding = 4.0
    size = r_outer_ring * 2 + padding * 2
    cx = size / 2.0
    cy = size / 2.0

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size:.2f}mm" height="{size:.2f}mm" '
        f'viewBox="0 0 {size:.4f} {size:.4f}">'
    )
    lines.append(
        "  <!-- Encoder wheel laser template — all dimensions in mm -->"
    )

    # Inline style: red = cut, blue = engrave
    lines.append("  <style>")
    lines.append('    .cut     { fill: none; stroke: #FF0000; stroke-width: 0.15; }')
    lines.append('    .engrave { fill: none; stroke: #0000FF; stroke-width: 0.10; stroke-dasharray: 0.5 0.5; }')
    lines.append("  </style>")

    # Group centred on the disc
    lines.append(f'  <g transform="translate({cx:.4f},{cy:.4f})">')

    # --- Outer disc ring (cut) ---
    lines.append(
        f'    <circle cx="0" cy="0" r="{r_outer_ring:.4f}" class="cut" />'
    )

    # --- Central shaft hole (cut) ---
    if center_hole:
        lines.append(
            f'    <circle cx="0" cy="0" r="{center_hole_radius:.4f}" class="cut" />'
        )

    # --- Magnet slots (cut, with kerf compensation) ---
    # Each slot is a rectangle expanded by `kerf` on every side so that
    # the magnet (exact size) fits snugly after the laser kerf is removed.
    hw = magnet_width / 2.0 + kerf          # half-width of the slot
    ir_slot = geo["inner_radius"] - kerf    # slot starts slightly inside r_inner
    slot_len = magnet_length + 2 * kerf     # slot radial length

    for i in range(n_magnets):
        angle = i * geo["angle_step"]

        def to_xy(r, t, a=angle):
            return (
                r * math.cos(a) - t * math.sin(a),
                r * math.sin(a) + t * math.cos(a),
            )

        pts = [
            to_xy(ir_slot, -hw),
            to_xy(ir_slot,  hw),
            to_xy(ir_slot + slot_len,  hw),
            to_xy(ir_slot + slot_len, -hw),
        ]
        d = _pts_to_path(pts)
        lines.append(f'    <path d="{d}" class="cut" />')

    # --- Inner radius reference circle (engrave) ---
    lines.append(
        f'    <circle cx="0" cy="0" r="{geo["inner_radius"]:.4f}" class="engrave" />'
    )

    # --- Pole-pair tick marks on the outer ring (engrave, optional) ---
    # One tick per magnet at the outer edge, to aid alignment when magnetising
    for i in range(n_magnets):
        angle = i * geo["angle_step"]
        r1 = r_outer_ring - 1.5
        r2 = r_outer_ring - 0.3
        x1 = r1 * math.cos(angle)
        y1 = r1 * math.sin(angle)
        x2 = r2 * math.cos(angle)
        y2 = r2 * math.sin(angle)
        lines.append(
            f'    <line x1="{x1:.4f}" y1="{y1:.4f}" '
            f'x2="{x2:.4f}" y2="{y2:.4f}" class="engrave" />'
        )

    lines.append("  </g>")

    # Parameter annotation
    note = (
        f"Encoder wheel: {n_magnets} magnets, "
        f"{magnet_length}\u00d7{magnet_width}\u00d7{magnet_thickness} mm, "
        f"r_inner={geo['inner_radius']:.2f} mm, "
        f"r_outer={geo['outer_radius']:.2f} mm, "
        f"disc \u00d8={(r_outer_ring * 2):.1f} mm.  "
        f"Red = cut, Blue = engrave.  Sheet thickness = {magnet_thickness} mm."
    )
    lines.append(
        f'  <text x="{padding:.1f}" y="{size - 1.5:.2f}" '
        f'font-family="monospace" font-size="1.8" fill="#444">{note}</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(
        description="Generate a laser-cutter SVG for an encoder wheel template.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--n-magnets", type=int, default=12, metavar="N",
                   help="Number of magnets (should be a multiple of 12)")
    p.add_argument("--length", type=float, default=20.0, metavar="mm",
                   help="Magnet radial length")
    p.add_argument("--width", type=float, default=5.0, metavar="mm",
                   help="Magnet tangential width")
    p.add_argument("--thickness", type=float, default=2.0, metavar="mm",
                   help="Magnet (and sheet) axial thickness")
    p.add_argument("--inner-radius", type=float, default=None, metavar="mm",
                   help="Inner radius (default = minimum, inner corners touching)")
    p.add_argument("--margin", type=float, default=3.0, metavar="mm",
                   help="Extra ring width beyond magnet tips")
    p.add_argument("--kerf", type=float, default=0.1, metavar="mm",
                   help="Laser kerf compensation per side")
    p.add_argument("--center-hole-radius", type=float, default=5.0, metavar="mm",
                   help="Central shaft hole radius")
    p.add_argument("--no-center-hole", action="store_true",
                   help="Omit the central shaft hole")
    p.add_argument("--output", default="encoder_wheel_laser.svg", metavar="FILE",
                   help="Output SVG filename")
    return p


def main():
    args = _build_parser().parse_args()

    svg = generate_laser_svg(
        n_magnets=args.n_magnets,
        magnet_length=args.length,
        magnet_width=args.width,
        magnet_thickness=args.thickness,
        inner_radius=args.inner_radius,
        margin=args.margin,
        kerf=args.kerf,
        center_hole=not args.no_center_hole,
        center_hole_radius=args.center_hole_radius,
    )

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(svg)

    geo = encoder_geometry(
        n_magnets=args.n_magnets,
        magnet_length=args.length,
        magnet_width=args.width,
        magnet_thickness=args.thickness,
        inner_radius=args.inner_radius,
    )
    r_out = geo["outer_radius"] + args.margin
    print(f"Wrote {args.output}")
    print(f"  Inner radius  : {geo['inner_radius']:.3f} mm")
    print(f"  Outer radius  : {geo['outer_radius']:.3f} mm")
    print(f"  Disc diameter : {r_out * 2:.2f} mm")


if __name__ == "__main__":
    main()
