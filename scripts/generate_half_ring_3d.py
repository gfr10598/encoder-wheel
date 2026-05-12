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
    # First magnet at angle 0 (Y=0, X>0) so cross-section passes through its centre
    start = 0.0
    single = make_single_magnet(data)
    magnets = []
    for i in range(data["magnets_per_half"]):
        angle = start + i * theta
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
# Printed cover — built subtractively
# ─────────────────────────────────────────────────────────────────────────────

def make_cover_blank(data: dict) -> Shape:
    """Solid half-ring annulus: cover ID → cover OD, z0 → z5.

    All material starts here; subsequent cuts define every feature.
    """
    cir = data["cover_inner_radius"]
    cor = data["cover_outer_radius"]
    z5  = data["z5"]
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            _semi_annulus_sketch(cir, cor)
        extrude(amount=z5)
    return p.part


def make_steel_cavity_void(data: dict) -> Shape:
    """Revolve of the full steel-ring cavity: seat + snap beads + chamfer.

    XZ polygon (cavity cross-section, CCW from +Y side):

        inner bottom (sir+clr, z2-clr)
        outer bottom (sor-clr, z2-clr)
        outer seat   (sor-clr, z3)
        outer snap   (sor-snap, z3)→(sor-snap, z4)   ← snap bead
        outer mouth  (sor+taper, z5)                  ← chamfer opens out
        inner mouth  (sir-taper, z5)                  ← chamfer opens in
        inner snap   (sir+snap, z4)→(sir+snap, z3)    ← snap bead
        inner seat   (sir+clr, z3)

    clr = 0.05 mm clearance on all faces.
    """
    sir, sor  = data["steel_inner_radius"], data["steel_outer_radius"]
    z2, z3, z4, z5 = data["z2"], data["z3"], data["z4"], data["z5"]
    snap  = data["snap_overhang"]   # 0.2 mm
    taper = data["chamfer_taper"]   # 1.2 mm
    clr   = 0.05                    # steel clearance

    xz = [
        (sir + clr,    z2 - clr),
        (sor - clr,    z2 - clr),
        (sor - clr,    z3),
        (sor - snap,   z3),
        (sor - snap,   z4),
        (sor + taper,  z5),
        (sir - taper,  z5),
        (sir + snap,   z4),
        (sir + snap,   z3),
        (sir + clr,    z3),
    ]
    return _revolve_xz_profile(xz)


def make_magnet_pocket_void(data: dict, index: int) -> Shape:
    """Single expanded magnet pocket void, with 0.05 mm clearance on all sides.

    The pocket is a Box aligned radially at angular position ``index``,
    spanning z1 (cavity floor) to z2+0.05 (top clearance).
    """
    mir   = data["magnet_inner_radius"]
    z1    = data["z1"]
    z2    = data["z2"]
    L     = data["magnet_length"] + 0.10  # radial:     20.10 mm
    W     = data["magnet_width"]  + 0.10  # tangential:  5.10 mm
    T     = (z2 - z1) + 0.05             # axial:        2.15 mm
    clr   = 0.05

    # Angle: 0° = first magnet at (X>0, Y=0); subsequent magnets CCW
    theta = data["pitch_angle"]
    angle = math.degrees(index * theta)

    with BuildPart() as p:
        Box(L, W, T, align=(Align.MIN, Align.CENTER, Align.MIN))
    void = p.part.moved(Location((mir - clr, 0.0, z1)))
    return void.rotate(Axis.Z, angle)


def make_magnet_dogbones(data: dict) -> Compound:
    """0.25 mm radius axial cylinders at all 4 base corners of every pocket.

    One cylinder per corner:  inner/outer radial face × both angular ends.
    Each cylinder spans z=0 → z=z2, clearing the floor corner so the magnet
    can seat without a radius-constrained interference fit.
    """
    mir    = data["magnet_inner_radius"] - 0.05   # expanded pocket inner face
    mor    = data["magnet_outer_radius"] + 0.05   # expanded pocket outer face
    W      = data["magnet_width"] + 0.10          # expanded pocket width
    z2     = data["z2"]
    r_dog  = data["dogbone_radius"]               # 0.25 mm
    theta  = data["pitch_angle"]

    with BuildPart() as tmpl:
        with BuildSketch(Plane.XY):
            Circle(r_dog)
        extrude(amount=z2 + r_dog)
    cyl = tmpl.part

    solids = []
    for i in range(data["magnets_per_half"]):
        angle = i * theta           # radians
        for r in (mir, mor):        # inner and outer radial pocket face
            for w in (-W / 2, +W / 2):   # both tangential ends
                # Corner position in lab frame
                x = r * math.cos(angle) - w * math.sin(angle)
                y = r * math.sin(angle) + w * math.cos(angle)
                solids.append(cyl.moved(Location((x, y, 0.0))))

    return Compound(solids)


def make_cover(data: dict) -> Shape:
    """Subtractive build: blank annulus → cut steel cavity → cut magnet pockets → cut dogbones."""
    print("  blank …", end=" ", flush=True)
    cover = make_cover_blank(data)

    print("steel cavity …", end=" ", flush=True)
    cover = cover.cut(make_steel_cavity_void(data))

    n = data["magnets_per_half"]
    print(f"magnet pockets (×{n}) …", end=" ", flush=True)
    for i in range(n):
        cover = cover.cut(make_magnet_pocket_void(data, i))

    print("dogbones …", end=" ", flush=True)
    cover = cover.cut(make_magnet_dogbones(data))

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

