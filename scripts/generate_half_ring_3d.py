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
    chamfer,
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


def _torus_cut(r_center: float, z_center: float, r_tube: float, n_pts: int = 24) -> Shape:
    """Half-torus (180°) formed by revolving a circle in XZ around Z.

    Creates a quarter-circle relief groove when intersected with a corner.
    r_center: radius of the circle centre from Z axis
    z_center: axial position of the circle centre
    r_tube  : radius of the cross-section circle (= dogbone_radius)
    """
    pts = [
        (r_center + r_tube * math.cos(i * math.tau / n_pts),
         z_center + r_tube * math.sin(i * math.tau / n_pts))
        for i in range(n_pts)
    ]
    return _revolve_xz_profile(pts)


# ─────────────────────────────────────────────────────────────────────────────
# Reference bodies  (not printed — used for intersection checks only)
# ─────────────────────────────────────────────────────────────────────────────

def make_single_magnet(data: dict) -> Shape:
    """One 20×5×2 mm magnet at angle=0, resting against the steel bottom face at z2.

    Corner rounds approximate real sintered magnet geometry:
      0.7 mm on the short (2 mm, Z-direction) edges
      0.3 mm on the longer (5 mm and 20 mm) edges
    """
    L   = data["magnet_length"]       # 20 mm radial
    W   = data["magnet_width"]        # 5 mm tangential
    T   = data["magnet_thickness"]    # 2 mm axial
    mir = data["magnet_inner_radius"]

    with BuildPart() as p:
        Box(L, W, T, align=(Align.MIN, Align.CENTER, Align.MIN))
        # Short (T=2 mm, Z-direction) edges — larger corner round
        short_edges = [e for e in p.edges() if e.length < T + 0.5]
        fillet(short_edges, radius=min(0.7, T / 2 - 0.01))
        # Longer (W=5 mm and L=20 mm) edges — smaller corner round
        long_edges = [e for e in p.edges() if e.length > T + 0.5]
        fillet(long_edges, radius=0.3)
    z_bottom = data["z2"] - T   # magnet hangs from steel bottom face at z2
    return p.part.moved(Location((mir, 0, z_bottom)))


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
    """1/8 in steel ring, Y>=0 half, occupying z2→z3.

    0.5 mm corner rounds on all edges to represent the ground/deburred
    edges of the real steel ring.
    """
    sir = data["steel_inner_radius"]
    sor = data["steel_outer_radius"]
    z2  = data["z2"]
    st  = data["steel_thickness"]
    with BuildPart() as p:
        with BuildSketch(Plane(origin=(0, 0, z2))):
            _semi_annulus_sketch(sir, sor)
        extrude(amount=st)
        fillet(p.edges(), radius=0.5)
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
    """Single expanded magnet pocket void with dogbone cylinders at the 4 vertical
    corner edges (where radial wall meets tangential end wall).

    The dogbone cylinders span z1 → z2+0.05 (same as the pocket) and do NOT
    go below z1, so the 1 mm base skin is never undercut.
    """
    mir   = data["magnet_inner_radius"]
    z1    = data["z1"]
    z2    = data["z2"]
    L     = data["magnet_length"] + 0.10  # radial:     20.10 mm
    W     = data["magnet_width"]  + 0.10  # tangential:  5.10 mm
    T     = (z2 - z1) + 0.05             # axial:        2.15 mm
    clr   = 0.05
    r_dog = data["dogbone_radius"]        # 0.25 mm

    mir_f = mir - clr                     # expanded inner radial face
    mor_f = mir_f + L                     # expanded outer radial face

    # ── Core rectangular void + dogbone cylinders ───────────────────
    # Build everything inside one BuildPart so all shapes are automatically
    # fused into a single solid.  BuildPart context-mode ADD is the default
    # for each extrude(), so the box and all 4 cylinders union into one body.
    with BuildPart() as p:
        Box(L, W, T, align=(Align.MIN, Align.CENTER, Align.MIN))
        # 4 corner cylinders — placed relative to box origin (mir_f, 0, z1)
        for cx_off in (0.0, L):
            for cy_off in (-W / 2, +W / 2):
                with BuildSketch(Plane(origin=(cx_off, cy_off, 0))):
                    Circle(r_dog)
                extrude(amount=T)
    void = p.part.moved(Location((mir_f, 0.0, z1)))

    # ── Rotate to pocket's angular position ──────────────────────────
    angle = math.degrees(index * data["pitch_angle"])
    return void.rotate(Axis.Z, angle)


def make_steel_corner_dogbones(data: dict) -> Compound:
    """Half-torus cuts at the two floor corners of the steel seat.

    The floor is at z = z2 - 0.05 mm (clearance gap below steel ring).
    Inner corner: torus at r = sir + 0.05, z = z2-0.05
    Outer corner: torus at r = sor - 0.05, z = z2-0.05
    Relieves the radius the printer leaves at each bottom corner so the
    steel ring seats fully against the cavity floor.
    """
    sir = data["steel_inner_radius"]
    sor = data["steel_outer_radius"]
    z2  = data["z2"]
    r   = data["dogbone_radius"]
    clr = 0.05
    z_floor = z2 - clr      # actual cavity floor level
    return Compound([
        _torus_cut(sir + clr, z_floor, r),
        _torus_cut(sor - clr, z_floor, r),
    ])


def make_snap_root_dogbones(data: dict) -> Compound:
    """Half-torus cuts at the base of each snap arm.

    The snap arm for the outer wall starts at (sor-snap, z3) in the XZ
    profile; the inner arm at (sir+snap, z3).  A torus at those points
    cuts into the PETG wall behind each snap face, creating a thin hinge
    line so the snap can flex inward/outward more easily.

    The torus extends ±r_dog in both radius and z.  The radial extent
    goes into the wall material (away from the cavity) — it does NOT
    touch the snap tooth face itself.  The axial extent goes 0.25 mm
    above z3 (into the snap arm) and 0.25 mm below z3 (into the seat,
    which is already void — no material removed there).
    """
    sir  = data["steel_inner_radius"]
    sor  = data["steel_outer_radius"]
    z3   = data["z3"]
    snap   = data["snap_overhang"]    # 0.2 mm (unused for torus position)
    r      = data["dogbone_radius"]   # 0.25 mm
    z_hinge = z3 - r   # torus centred here → top of circle tangent to z3
                        # so the entire torus body sits below the snap arm
    # Tori aligned on the steel face (sor / sir), not on the snap edge:
    # the hinge groove must be at the point where the PETG wall transitions
    # from the flat steel seat to the snap arm — that is the steel face.
    return Compound([
        _torus_cut(sor, z_hinge, r),   # outer snap root — at steel OD
        _torus_cut(sir, z_hinge, r),   # inner snap root — at steel ID
    ])


def make_cover(data: dict) -> Shape:
    """Subtractive build: blank → steel cavity → magnet pockets → dogbones → bevels.

    Each magnet pocket void is a Compound of the rectangular box and 4 dogbone
    cylinders at its vertical corner edges.  Steel-corner and snap-root tori
    are cut separately (they are full-ring revolutions).  Finally 0.2 mm
    bevels are applied to all convex edges of the PETG exterior.
    """
    print("  blank …", end=" ", flush=True)
    cover = make_cover_blank(data)

    print("steel cavity …", end=" ", flush=True)
    cover = cover.cut(make_steel_cavity_void(data))

    n = data["magnets_per_half"]
    print(f"magnet pockets (×{n}, with dogbones) …", end=" ", flush=True)
    for i in range(n):
        cover = cover.cut(make_magnet_pocket_void(data, i))

    print("steel corner dogbones …", end=" ", flush=True)
    cover = cover.cut(make_steel_corner_dogbones(data))

    print("snap root dogbones …", end=" ", flush=True)
    cover = cover.cut(make_snap_root_dogbones(data))

    print("PETG bevels …", end=" ", flush=True)
    z5 = data["z5"]
    # Chamfer only the circular arcs on the top and bottom exterior faces.
    # Straight edges at Y≈0 (the half-ring cut plane) have only one adjacent
    # face and will cause OCCT to abort, so we skip them.
    bevel_edges = [
        e for e in cover.edges()
        if (abs(e.center().Z) < 0.15 or abs(e.center().Z - z5) < 0.15)
        and e.center().Y > 1.0    # exclude Y=0 boundary edges
    ]
    if bevel_edges:
        try:
            cover = chamfer(bevel_edges, length=0.2)
        except Exception as exc:
            print(f"(skipped — {exc})", end=" ", flush=True)

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
    parser.add_argument("--no-step", action="store_true", help="Skip STEP export")
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

    if not args.no_step:
        path = output_dir / "half_ring_cover.step"
        export_step(cover, str(path))
        print(f"  → {path}")


if __name__ == "__main__":
    main()

