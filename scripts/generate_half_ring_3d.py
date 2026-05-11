#!/usr/bin/env python3
"""
Build a parametric 3D model of the 10 in half-ring magnet cover using build123d.

Architecture
------------
Each physical component is built by its own function so that geometry can be
inspected and modified independently:

    make_single_magnet()        20×5×2 mm magnet (reference body)
    make_magnet_array()         45 reference magnets positioned on the ring
    make_steel_half_ring()      1/8 in steel backing ring (reference body)
    make_base()                 1 mm printed base skin
    make_inner_wall()           inner capture wall with chamfer + snap tooth
    make_outer_wall()           outer capture wall (tab pockets TBD)
    make_magnet_separators()    radial walls between adjacent magnets
    make_cover()                union of all printed components
    check_no_intersections()    assert reference bodies don't overlap cover

Coordinate system (print orientation — part prints flat, base on bed)
----------------------------------------------------------------------
    Z = 0      print-bed face (bottom of base skin)
    Z = z1     top of base / cavity floor
    Z = z2     top of magnet clearance zone
    Z = z3     steel ring seat (top of steel in cavity)
    Z = z4     top of chamfer lead-in (mouth of cavity)
    Z = z5     snap tooth tip (top of walls, open end of cavity)

    X,Y plane = ring plane;  rotation axis = Z
    The printed half ring occupies Y >= 0 (upper semicircle).

Assembly: flip cover so Z=0 faces outward; steel ring enters from Z=z5 end.

Snap geometry
-------------
    z3→z4  chamfer: cavity face flares outward by chamfer_taper (1.2 mm)
    z4→z5  snap tooth: snaps back inward, ending 0.2 mm inside steel edge

Fillets
-------
    Magnet cavity corners: magnet_pocket_fillet (0.5 mm) — larger than the
    expected magnet corner radius so magnets seat fully without interference.
    Cover outer edges: 0.2 mm cosmetic break.
    Snap tooth edges: not filleted (must grip).

Usage
-----
    conda run -n base python scripts/generate_half_ring_3d.py [--step] [--check-intersections]
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from generate_half_ring_docs import INCH, design_data

from build123d import (
    Align,
    Axis,
    Box,
    BuildPart,
    BuildSketch,
    Circle,
    Compound,
    Edge,
    Face,
    Location,
    Mode,
    Plane,
    Rectangle,
    Shape,
    Solid,
    Wire,
    export_step,
    export_stl,
    extrude,
    fillet,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _semi_annulus_sketch(r_inner: float, r_outer: float) -> None:
    """Add a Y>=0 semi-annular face to the active BuildSketch."""
    clip_w = (r_outer + 2) * 2
    Circle(r_outer)
    Circle(r_inner, mode=Mode.SUBTRACT)
    Rectangle(clip_w, r_outer * 2, align=(Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)


def _revolve_xz_profile(xz_pts: list[tuple[float, float]], arc_deg: float = 180.0) -> Shape:
    """Revolve a closed XZ-plane polygon around the Z axis.

    Parameters
    ----------
    xz_pts  : (x, z) pairs, counterclockwise from +Y side. All x > 0.
    arc_deg : revolution arc (default 180 = half ring).
    """
    pts_3d = [(x, 0.0, z) for x, z in xz_pts]
    n = len(pts_3d)
    edges = [Edge.make_line(pts_3d[i], pts_3d[(i + 1) % n]) for i in range(n)]
    wire = Wire(edges)
    face = Face(wire)
    return Solid.revolve(face, arc_deg, Axis.Z)


# ─────────────────────────────────────────────────────────────────────────────
# Reference bodies  (not printed — used for intersection checks only)
# ─────────────────────────────────────────────────────────────────────────────

def make_single_magnet(data: dict) -> Shape:
    """One 20x5x2 mm magnet at angle=0, in the cavity at z=z1.

    Conservative 0.2 mm fillets on all edges — must be smaller than the
    smallest expected magnet corner radius so the cavity check is valid.
    """
    L   = data["magnet_length"]       # 20 mm radial
    W   = data["magnet_width"]        # 5 mm tangential
    T   = data["magnet_thickness"]    # 2 mm axial
    mir = data["magnet_inner_radius"]
    z1  = data["z1"]

    with BuildPart() as p:
        Box(L, W, T, align=(Align.MIN, Align.CENTER, Align.MIN))
        fillet(p.edges(), radius=0.2)
    return p.part.moved(Location((mir, 0, z1)))


def make_magnet_array(data: dict) -> Compound:
    """45 reference magnets around the Y>=0 half ring."""
    theta = data["pitch_angle"]
    start = math.pi - theta / 2.0
    single = make_single_magnet(data)
    magnets = []
    for i in range(data["magnets_per_half"]):
        angle = start - i * theta
        magnets.append(single.rotate(Axis.Z, math.degrees(angle)))
    return Compound(magnets)


def make_steel_half_ring(data: dict) -> Shape:
    """1/8 in steel ring, Y>=0 half, occupying z2→z3."""
    sir = data["steel_inner_radius"]
    sor = data["steel_outer_radius"]
    z2  = data["z2"]
    st  = data["steel_thickness"]
    with BuildPart() as p:
        with BuildSketch(Plane(origin=(0, 0, z2))):
            _semi_annulus_sketch(sir, sor)
        extrude(amount=st)
    return p.part


# ─────────────────────────────────────────────────────────────────────────────
# Printed components
# ─────────────────────────────────────────────────────────────────────────────

def make_base(data: dict) -> Shape:
    """1 mm base skin, full cover radial span, z0→z1."""
    cir = data["cover_inner_radius"]
    cor = data["cover_outer_radius"]
    z1  = data["z1"]
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            _semi_annulus_sketch(cir, cor)
        extrude(amount=z1)
    return p.part


def make_inner_wall(data: dict) -> Shape:
    """Inner capture wall with chamfer and snap tooth, revolved 180°.

    XZ profile (counterclockwise, viewed from +Y):

        cir,z1 ──── sir,z1        (bottom — cavity floor level)
                      |
                    sir,z3        (straight up to steel seat)
                     ╱
               sir-taper,z4       (chamfer flares cavity INWARD → wider opening)
                       ╲
               sir-snap,z5        (snap tooth grips inside steel ID)
        cir,z5 ──────────

    snap  = 0.2 mm (snap_overhang)
    taper = 1.2 mm (chamfer_taper)
    At z4: cavity face is 1.2 mm inward of steel ID → wider opening guides ring in.
    At z5: snap is 0.2 mm inward of steel ID → grips ring after it passes z4 peak.
    """
    cir   = data["cover_inner_radius"]
    sir   = data["steel_inner_radius"]
    z1, z3, z4, z5 = data["z1"], data["z3"], data["z4"], data["z5"]
    snap  = data["snap_overhang"]
    taper = data["chamfer_taper"]

    xz = [
        (cir,          z1),
        (sir,          z1),
        (sir,          z3),
        (sir - taper,  z4),
        (sir - snap,   z5),
        (cir,          z5),
    ]
    return _revolve_xz_profile(xz)


def make_outer_wall(data: dict) -> Shape:
    """Outer capture wall with chamfer and snap tooth, revolved 180°.

    Mirror of inner wall: taper opens inward, snap grips outside steel OD.

    XZ profile (counterclockwise, viewed from +Y):

        sor,z1 ──── cor,z1
          |
        sor,z3              (straight up to steel seat)
             ╲
        sor+taper,z4        (chamfer flares cavity OUTWARD → wider opening)
         ╱
    sor-snap,z5             (snap grips outside steel OD)
        cor,z5 ──────────
    """
    cor   = data["cover_outer_radius"]
    sor   = data["steel_outer_radius"]
    z1, z3, z4, z5 = data["z1"], data["z3"], data["z4"], data["z5"]
    snap  = data["snap_overhang"]
    taper = data["chamfer_taper"]

    xz = [
        (sor,          z1),
        (cor,          z1),
        (cor,          z5),
        (sor - snap,   z5),
        (sor + taper,  z4),
        (sor,          z3),
    ]
    return _revolve_xz_profile(xz)


def make_magnet_separators(data: dict) -> Compound | None:
    """Radial walls between adjacent magnets, occupying z1→z2.

    Each separator fills the inter-magnet angular gap at the steel ring radii.
    Returns a Compound of 44 wedge-shaped solids (or None if too narrow).
    """
    sir   = data["steel_inner_radius"]
    sor   = data["steel_outer_radius"]
    z1    = data["z1"]
    z2    = data["z2"]
    theta = data["pitch_angle"]
    W     = data["magnet_width"]

    mid_r = (sir + sor) / 2.0
    half_magnet_arc = math.asin(min(W / 2.0 / mid_r, 1.0))
    sep_half_arc = theta / 2.0 - half_magnet_arc

    if sep_half_arc <= 0:
        print("  warning: no room for magnet separators at this pitch")
        return None

    start = math.pi - theta / 2.0
    solids = []
    for i in range(data["magnets_per_half"] - 1):
        gap_centre = start - i * theta - theta / 2.0
        a_start = gap_centre - sep_half_arc
        arc_deg = math.degrees(2.0 * sep_half_arc)
        xz = [(sir, z1), (sor, z1), (sor, z2), (sir, z2)]
        pts_3d = [(x, 0.0, z) for x, z in xz]
        edges = [Edge.make_line(pts_3d[j], pts_3d[(j + 1) % 4]) for j in range(4)]
        face = Face(Wire(edges))
        sep = Solid.revolve(face, arc_deg, Axis.Z)
        sep = sep.rotate(Axis.Z, math.degrees(a_start))
        solids.append(sep)

    return Compound(solids)


def make_cover(data: dict) -> Shape:
    """Fuse all printed components into one cover body."""
    print("    base …", end=" ", flush=True)
    base = make_base(data)
    print("inner wall …", end=" ", flush=True)
    inner = make_inner_wall(data)
    print("outer wall …", end=" ", flush=True)
    outer = make_outer_wall(data)
    print("separators …", end=" ", flush=True)
    seps = make_magnet_separators(data)
    print("fusing …", end=" ", flush=True)
    cover = base.fuse(inner).fuse(outer)
    if seps is not None:
        cover = cover.fuse(seps)
    print("done.")
    return cover


# ─────────────────────────────────────────────────────────────────────────────
# Intersection check
# ─────────────────────────────────────────────────────────────────────────────

def check_no_intersections(named_parts: dict[str, Shape], tol: float = 0.01) -> None:
    """Raise ValueError if any two shapes share volume > tol mm³."""
    items = list(named_parts.items())
    for i, (n1, p1) in enumerate(items):
        for n2, p2 in items[i + 1:]:
            overlap = p1 & p2
            vol = getattr(overlap, "volume", 0.0) or 0.0
            if vol > tol:
                raise ValueError(
                    f"Intersection: {n1} ∩ {n2} = {vol:.4f} mm³  (tol={tol})"
                )
    print(f"  ✓ No intersections among {len(items)} parts.")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate half-ring cover STL/STEP")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--step", action="store_true")
    parser.add_argument("--no-stl", action="store_true")
    parser.add_argument(
        "--check-intersections", action="store_true",
        help="Build reference bodies and verify no overlaps with cover (slow)",
    )
    args = parser.parse_args()

    if args.output_dir is None:
        output_dir = Path(__file__).resolve().parents[1] / "examples"
    else:
        output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = design_data()
    print(
        f"Half-ring cover  ID={2*data['cover_inner_radius']/INCH:.3f} in  "
        f"OD={2*data['cover_outer_radius']/INCH:.3f} in\n"
        f"  Z: base={data['z1']:.2f}  magnet={data['z2']:.2f}  "
        f"steel={data['z3']:.3f}  chamfer={data['z4']:.3f}  snap={data['z5']:.3f} mm"
    )

    cover = make_cover(data)

    if args.check_intersections:
        print("  Building reference bodies …")
        magnets = make_magnet_array(data)
        steel   = make_steel_half_ring(data)
        check_no_intersections({"cover": cover, "magnets": magnets, "steel": steel})

    if not args.no_stl:
        path = output_dir / "half_ring_cover.stl"
        export_stl(cover, str(path))
        print(f"  → {path}")

    if args.step:
        path = output_dir / "half_ring_cover.step"
        export_step(cover, str(path))
        print(f"  → {path}")


if __name__ == "__main__":
    main()

