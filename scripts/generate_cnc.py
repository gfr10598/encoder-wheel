#!/usr/bin/env python3
"""
Generate a DXF file for CNC machining an encoder-wheel disc.

The output (DXF R12 format, no external dependencies) contains:

  Layer BOUNDARY  — outer disc circle (profile to cut)
  Layer BORE      — central shaft bore circle
  Layer POCKETS   — rectangular magnet pocket outlines
                    (machine these as pockets to magnet_thickness depth)
  Layer REFERENCE — inner radius reference circle (do not cut)

Toolpath hints
--------------
  • Machine the POCKETS first as pockets to the magnet depth.
  • Then cut the BORE.
  • Finally profile-cut the BOUNDARY.
  • The REFERENCE circle is for visual reference only.

Usage
-----
    python scripts/generate_cnc.py [options]

Options
-------
  --n-magnets N      Number of magnets (multiple of 12, default 12)
  --length L         Magnet radial length in mm (default 20)
  --width W          Magnet tangential width in mm (default 5)
  --thickness T      Magnet axial thickness in mm — pocket depth (default 2)
  --inner-radius R   Inner radius in mm (default = minimum)
  --margin M         Outer disc margin beyond magnet tips in mm (default 3)
  --center-bore R    Radius of central bore in mm (default 5)
  --clearance C      Per-side clearance added to pocket dims (default 0.1)
  --output FILE      Output DXF filename (default encoder_wheel_cnc.dxf)
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import encoder_geometry


# ---------------------------------------------------------------------------
# Minimal DXF R12 writer (no external libraries required)
# ---------------------------------------------------------------------------

class _DXF:
    """Build a minimal DXF R12 file with CIRCLE and LWPOLYLINE entities."""

    def __init__(self):
        self._entities: list[str] = []

    def add_circle(self, cx: float, cy: float, r: float, layer: str = "0") -> None:
        self._entities.append(
            f"  0\nCIRCLE\n"
            f"  8\n{layer}\n"
            f" 10\n{cx:.6f}\n"
            f" 20\n{cy:.6f}\n"
            f" 30\n0.000000\n"
            f" 40\n{r:.6f}\n"
        )

    def add_lwpolyline(
        self,
        points: list,
        closed: bool = True,
        layer: str = "0",
    ) -> None:
        flag = "1" if closed else "0"
        header = (
            f"  0\nLWPOLYLINE\n"
            f"  8\n{layer}\n"
            f" 90\n{len(points)}\n"
            f" 70\n{flag}\n"
        )
        body = "".join(
            f" 10\n{x:.6f}\n 20\n{y:.6f}\n" for x, y in points
        )
        self._entities.append(header + body)

    def add_line(
        self,
        x1: float, y1: float,
        x2: float, y2: float,
        layer: str = "0",
    ) -> None:
        self._entities.append(
            f"  0\nLINE\n"
            f"  8\n{layer}\n"
            f" 10\n{x1:.6f}\n 20\n{y1:.6f}\n 30\n0.000000\n"
            f" 11\n{x2:.6f}\n 21\n{y2:.6f}\n 31\n0.000000\n"
        )

    def as_string(self) -> str:
        sections = [
            "  0\nSECTION\n  2\nHEADER\n",
            "  9\n$ACADVER\n  1\nAC1009\n",
            "  0\nENDSEC\n",
            "  0\nSECTION\n  2\nENTITIES\n",
        ]
        sections.extend(self._entities)
        sections.append("  0\nENDSEC\n  0\nEOF\n")
        return "".join(sections)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate_cnc_dxf(
    n_magnets: int = 12,
    magnet_length: float = 20.0,
    magnet_width: float = 5.0,
    magnet_thickness: float = 2.0,
    inner_radius: float = None,
    disc_margin: float = 3.0,
    center_bore: float = 5.0,
    clearance: float = 0.1,
) -> str:
    """Generate DXF content for CNC machining.

    Parameters
    ----------
    n_magnets : int
        Number of magnets.
    magnet_length : float
        Radial length of each magnet (mm).
    magnet_width : float
        Tangential width of each magnet (mm).
    magnet_thickness : float
        Axial thickness of each magnet (mm) — sets pocket depth.
    inner_radius : float, optional
        Inner radius (mm); defaults to minimum (inner corners touching).
    disc_margin : float
        Outer disc margin beyond the magnet tips (mm).
    center_bore : float
        Central shaft bore radius (mm).
    clearance : float
        Per-side clearance added to each pocket dimension for easy fit (mm).

    Returns
    -------
    str
        DXF R12 file content.
    """
    geo = encoder_geometry(
        n_magnets=n_magnets,
        magnet_length=magnet_length,
        magnet_width=magnet_width,
        magnet_thickness=magnet_thickness,
        inner_radius=inner_radius,
    )

    dxf = _DXF()

    # Outer disc boundary
    dxf.add_circle(0.0, 0.0, geo["outer_radius"] + disc_margin, layer="BOUNDARY")

    # Central bore
    dxf.add_circle(0.0, 0.0, center_bore, layer="BORE")

    # Inner radius reference circle
    dxf.add_circle(0.0, 0.0, geo["inner_radius"], layer="REFERENCE")

    # Magnet pockets — slightly larger than the magnet for easy assembly
    hw = magnet_width / 2.0 + clearance        # half-width of pocket
    ir_pkt = geo["inner_radius"] - clearance   # pocket inner edge
    pkt_len = magnet_length + 2.0 * clearance  # pocket radial length

    for i in range(n_magnets):
        angle = i * geo["angle_step"]

        def to_xy(r, t, a=angle):
            return (
                r * math.cos(a) - t * math.sin(a),
                r * math.sin(a) + t * math.cos(a),
            )

        pts = [
            to_xy(ir_pkt, -hw),
            to_xy(ir_pkt,  hw),
            to_xy(ir_pkt + pkt_len,  hw),
            to_xy(ir_pkt + pkt_len, -hw),
        ]
        dxf.add_lwpolyline(pts, closed=True, layer="POCKETS")

    return dxf.as_string()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(
        description="Generate a DXF file for CNC machining an encoder-wheel disc.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--n-magnets", type=int, default=12, metavar="N")
    p.add_argument("--length", type=float, default=20.0, metavar="mm",
                   help="Magnet radial length")
    p.add_argument("--width", type=float, default=5.0, metavar="mm",
                   help="Magnet tangential width")
    p.add_argument("--thickness", type=float, default=2.0, metavar="mm",
                   help="Magnet axial thickness (= pocket depth)")
    p.add_argument("--inner-radius", type=float, default=None, metavar="mm",
                   help="Inner radius (default = minimum)")
    p.add_argument("--margin", type=float, default=3.0, metavar="mm",
                   help="Extra outer disc margin beyond magnet tips")
    p.add_argument("--center-bore", type=float, default=5.0, metavar="mm",
                   help="Central shaft bore radius")
    p.add_argument("--clearance", type=float, default=0.1, metavar="mm",
                   help="Per-side pocket clearance for easy fit")
    p.add_argument("--output", default="encoder_wheel_cnc.dxf", metavar="FILE")
    return p


def main():
    args = _build_parser().parse_args()

    dxf_text = generate_cnc_dxf(
        n_magnets=args.n_magnets,
        magnet_length=args.length,
        magnet_width=args.width,
        magnet_thickness=args.thickness,
        inner_radius=args.inner_radius,
        disc_margin=args.margin,
        center_bore=args.center_bore,
        clearance=args.clearance,
    )

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(dxf_text)

    geo = encoder_geometry(
        n_magnets=args.n_magnets,
        magnet_length=args.length,
        magnet_width=args.width,
        magnet_thickness=args.thickness,
        inner_radius=args.inner_radius,
    )
    r_disc = geo["outer_radius"] + args.margin
    print(f"Wrote {args.output}")
    print(f"  Inner radius  : {geo['inner_radius']:.3f} mm")
    print(f"  Outer radius  : {geo['outer_radius']:.3f} mm")
    print(f"  Disc diameter : {r_disc * 2:.2f} mm")
    print(f"  Pocket depth  : {args.thickness:.2f} mm")
    print(f"  Layers: BOUNDARY, BORE, POCKETS, REFERENCE")


if __name__ == "__main__":
    main()
