#!/usr/bin/env python3
"""Magnet pocket ring cell — single printed cell holding one magnet.

Geometry
--------
The ring is assembled from `magnet_count` identical cells.  Each cell is a
hollow cylinder sector spanning 360/magnet_count degrees, centred on θ=0.

Coordinate system
-----------------
  Z axis  = ring axis, Z=0 at axial centre of cell.
  +X at θ=0 = radial outward direction for magnet #0.
  Magnet inner face is flush with the bore surface (R_i).

Usage
-----
  .venv/bin/python magnet_pocket/generate.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import yaml
from build123d import (
    Axis,
    Box,
    BuildPart,
    Edge,
    Face,
    GeomType,
    Location,
    Mode,
    Rotation,
    Solid,
    Wire,
    add,
    export_step,
    fillet,
    offset,
)

CONFIG = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG) as f:
        return yaml.safe_load(f)


# ── magnet reference body ─────────────────────────────────────────────────────


def make_magnet(cfg: dict, shrink: float = 0.0) -> Solid:
    """Filleted magnet box centred at origin.  Radial=+X, tangential=Y, axial=Z.

    shrink: reduce each face inward by this amount before filleting.
    Call .moved() to position it in the ring.
    """
    m = cfg["magnet"]
    s2 = 2 * shrink
    with BuildPart() as bp:
        Box(m["radial_mm"] - s2, m["tangential_mm"] - s2, m["axial_mm"] - s2)
        # Radial (X-parallel) edges get the larger fillet first
        fillet(bp.edges().filter_by(Axis.X), m["edge_radius_radial_mm"])
        # Tangential and axial edges get the smaller fillet
        fillet(
            bp.edges().filter_by(Axis.Y) + bp.edges().filter_by(Axis.Z),
            m["edge_radius_other_mm"],
        )
    return bp.part


# ── cell ──────────────────────────────────────────────────────────────────────


def make_cell(cfg: dict) -> tuple[Solid, Solid]:
    """Build one cell body and its seated magnet.

    Returns
    -------
    cell : Solid
        Hollow cylinder sector with magnet pocket subtracted, centred on θ=0.
    magnet : Solid
        Filleted magnet at its seated position (inner face flush with bore).
    """
    m = cfg["magnet"]
    h = cfg["holder"]

    R_i = h["ID_mm"] / 2
    R_o = R_i + h["thickness_mm"]
    H = m["axial_mm"] + 2 * h["end_face_mm"]
    span_deg = 360.0 / h["magnet_count"]
    cl = h["clearance_mm"]

    # ── hollow cylinder sector ────────────────────────────────────────────────
    # Revolve a rectangle in the XZ plane around Z, then centre on θ=0.
    xz_pts = [(R_i, -H / 2), (R_o, -H / 2), (R_o, H / 2), (R_i, H / 2)]
    pts_3d = [(x, 0.0, z) for x, z in xz_pts]
    n = len(pts_3d)
    sec_edges = [Edge.make_line(pts_3d[i], pts_3d[(i + 1) % n]) for i in range(n)]
    sector = Solid.revolve(Face(Wire(sec_edges)), span_deg, Axis.Z)
    sector = sector.moved(Rotation(0, 0, -span_deg / 2))

    # ── positioned magnet ─────────────────────────────────────────────────────
    magnet = make_magnet(cfg)
    # Shift magnet outward by cl so the pocket inner face (magnet face − cl)
    # lands exactly on the bore surface (R_i), tangent to the ID.
    magnet_r = R_i + m["radial_mm"] / 2 + cl
    positioned_magnet = magnet.moved(Location((magnet_r, 0, 0)))

    # ── lead-in frustrum fused onto the magnet in its local frame ────────────
    # Inner station: bisect the magnet with a plane at z_inner; the cut face
    # carries the exact filleted profile (Z-edge fillets rounded corners).
    # Outer station: polygon + fillet_2d at z_outer — a uniform outward offset.
    taper_in = 2.0  # mm inside from +Z end (local Z = +8)
    taper_len = 5.0  # mm along axis to the wide end (local Z = +13)
    lead_in_cl = 1.0  # mm expansion on each side
    r0 = m["edge_radius_other_mm"]  # magnet corner radius (Z-edge fillet)

    z_inner = m["axial_mm"] / 2 - taper_in  # +8
    z_outer = z_inner + taper_len  # +13

    # Bisect: cut everything above z_inner away and take the new flat face.
    cutter_slab = Box(1000, 1000, 1000).moved(Location((0, 0, z_inner + 500)))
    magnet_lower = magnet.cut(cutter_slab)
    cs_face = max(
        (f for f in magnet_lower.faces() if abs(f.center().Z - z_inner) < 0.1),
        key=lambda f: f.area,
    )
    w_inner = cs_face.outer_wire()

    # Outer station: filleted rectangle built at Z=0, then moved to z_outer.
    dx_out = m["radial_mm"] + 2 * lead_in_cl
    dy_out = m["tangential_mm"] + 2 * lead_in_cl
    r_out = r0 + lead_in_cl
    hw, hh = dx_out / 2, dy_out / 2
    rect = Wire.make_polygon(
        [(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)], close=True
    )
    w_outer = rect.fillet_2d(r_out, rect.vertices()).moved(Location((0, 0, z_outer)))

    taper_frustrum = Solid.make_loft([w_inner, w_outer])

    with BuildPart() as cutter_bp:
        add(magnet)
        add(taper_frustrum)
    magnet_with_taper = cutter_bp.part

    # ── pocket = positioned magnet expanded by clearance ─────────────────────
    with BuildPart() as pocket_bp:
        add(positioned_magnet)
        offset(amount=cl)
    pocket = pocket_bp.part

    # ── sector with filleted end arcs, then pocket subtracted ─────────────────
    end_z = H / 2
    fillet_r = min(h["end_face_mm"] / 4, 0.5)
    with BuildPart() as bp:
        add(sector)
        end_arcs = [
            e
            for e in bp.edges()
            if abs(abs(e.center().Z) - end_z) < 0.01 and e.geom_type == GeomType.CIRCLE
        ]
        if end_arcs:
            fillet(end_arcs, fillet_r)
        add(pocket, mode=Mode.SUBTRACT)
        # ── axial insertion opening: tilted cutter through the +Z end face ────
        # Pivot at the bore-side inner face at the BOTTOM of the cutter so the
        # bottom inner edge stays on the bore wall regardless of tilt angle.
        # Cutter centre is only 2 mm above the holder midplane (Z=0); the tilt
        # is derived from the desired rim thickness at the holder face (Z=+12):
        #   rim = R_o − outer_face − face_shift  →  face_shift = R_o − outer_face − rim_target
        #   tilt = atan(face_shift / (H/2 − pivot_z))
        insertion_Z = 2.0  # cutter centre Z in cell frame
        pivot_x = R_i + cl  # bore-side face (radial)
        pivot_z = insertion_Z - m["axial_mm"] / 2  # = −8 (cutter bottom)
        rim_target = 1.6  # desired end-face rim (mm)
        outer_face = magnet_r + cl + m["radial_mm"] / 2  # = 56.0 mm
        face_shift = R_o - outer_face - rim_target  # = 1.2 mm
        face_to_pivot = H / 2 - pivot_z  # = 20 mm
        tilt_deg = math.degrees(math.atan(face_shift / face_to_pivot))
        insertion_cutter = (
            magnet_with_taper.moved(Location((magnet_r + cl, 0, insertion_Z)))
            .moved(Location((-pivot_x, 0, -pivot_z)))
            .moved(Rotation(0, tilt_deg, 0))
            .moved(Location((pivot_x, 0, pivot_z)))
        )
        add(insertion_cutter, mode=Mode.SUBTRACT)
        # ── fillet all remaining sharp (linear) edges to 0.1 mm ──────────────
        sharp = [
            e for e in bp.edges() if e.geom_type == GeomType.LINE and e.length >= 0.1
        ]
        if sharp:
            try:
                fillet(sharp, 0.1)
            except Exception:
                # Batch failed (face-consumption); apply one at a time, skip failures
                skipped = 0
                for e in sharp:
                    try:
                        fillet([e], 0.1)
                    except Exception:
                        skipped += 1
                if skipped:
                    print(f"  fillet: skipped {skipped}/{len(sharp)} edges")

    return bp.part, positioned_magnet


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    cfg = load_config()

    sys.path.insert(0, str(Path(__file__).parent))
    from validate_config import validate

    failures = validate(cfg)
    if failures:
        print(f"\nConfig validation failed: {', '.join(failures)}")
        sys.exit(1)

    print("\nBuilding cell...")
    cell, magnet = make_cell(cfg)

    try:
        from ocp_vscode import Camera, show, set_port  # type: ignore[import]

        set_port(3939)
        bb = cell.bounding_box()
        c = bb.center()
        view_offset = Location((-c.X, -c.Y, -c.Z))
        show(
            cell.moved(view_offset),
            magnet.moved(view_offset),
            names=["cell", "magnet"],
            colors=["#6baed6", "#cccccc"],
            alphas=[0.7, 1.0],
            reset_camera=Camera.CENTER,
        )
    except ImportError:
        pass

    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)
    export_step(cell, str(out_dir / "cell.step"))
    export_step(magnet, str(out_dir / "magnet.step"))
    print(f"Exported → {out_dir}/")


if __name__ == "__main__":
    main()
