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
    ins = cfg["insertion"]

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
    # inset keeps the pocket inner face inset_mm above R_i, leaving a
    # printable wall between the bore and the pocket floor.
    # cl/2 per side so the total pocket clearance equals clearance_mm.
    inset = h["inset_mm"]
    magnet_r = R_i + m["radial_mm"] / 2 + cl / 2 + inset
    positioned_magnet = magnet.moved(Location((magnet_r, 0, 0)))

    # ── lead-in frustrum fused onto the magnet in its local frame ────────────
    # Inner station: bisect the magnet with a plane at z_inner; the cut face
    # carries the exact filleted profile (Z-edge fillets rounded corners).
    # Outer station: polygon + fillet_2d at z_outer — a uniform outward offset.
    taper_in = ins["frustrum_depth_mm"]
    taper_len = ins["taper_len_mm"]
    lead_in_cl = ins["taper_expand_mm"]
    r0 = m["edge_radius_other_mm"]  # magnet corner radius (Z-edge fillet)

    # z_inner is in the cutter's local frame (origin = insertion_Z in cell frame).
    # frustrum_depth is measured back from the holder end face (H/2 in cell frame).
    insertion_Z = ins["cutter_z_mm"]
    z_inner = H / 2 - taper_in - insertion_Z
    z_outer = z_inner + taper_len  # +13

    # Apply clearance to the magnet body first so the frustum inner profile matches
    # the pocket walls exactly.
    with BuildPart() as magnet_cl_bp:
        add(magnet)
        offset(amount=cl / 2)
    magnet_cleared = magnet_cl_bp.part

    # Bisect: cut everything above z_inner away and take the new flat face.
    cutter_slab = Box(1000, 1000, 1000).moved(Location((0, 0, z_inner + 500)))
    magnet_lower = magnet_cleared.cut(cutter_slab)
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
        add(magnet_cleared)
        add(taper_frustrum)
    magnet_with_taper = cutter_bp.part

    # ── pocket = positioned magnet expanded by clearance ─────────────────────
    with BuildPart() as pocket_bp:
        add(positioned_magnet)
        offset(amount=cl / 2)  # cl/2 per side → total pocket clearance = clearance_mm
    pocket = pocket_bp.part

    # ── bore slot: pre-filleted so cavity corners are rounded after subtraction
    bore_slot_depth = 4.0  # mm into the wall
    with BuildPart() as slot_bp:
        Box(
            bore_slot_depth * 2,  # straddles bore: depth outside + depth inside
            4.0,                  # tangential: 4 mm centred on pocket
            m["axial_mm"],        # axial: full magnet length
        )
        fillet(slot_bp.edges(), 0.5)
    bore_slot = slot_bp.part.moved(Location((R_i, 0, 0)))

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
        # Pivot at the pocket inner face (bore-side) so the inner edge at the
        # pivot Z stays fixed.  Tilt is chosen so the inner rim at the end face
        # (Z=H/2) equals rim_target_mm:
        #   inner_rim = inset + sin(tilt) * face_to_pivot = rim_target
        #   face_shift = rim_target - inset
        #   tilt = atan(face_shift / face_to_pivot)
        # insertion_Z already defined above (used for frustum placement).
        pivot_x = R_i + cl / 2 + inset  # pocket inner face (bore-side)
        pivot_z = insertion_Z - m["axial_mm"] / 2
        rim_target = ins["rim_target_mm"]
        face_shift = rim_target - inset  # inward rim expansion at end face
        face_to_pivot = H / 2 - pivot_z
        tilt_deg = math.degrees(math.atan(face_shift / face_to_pivot))
        outer_face = magnet_r + m["radial_mm"] / 2 + cl / 2  # pocket outer face
        insertion_cutter = (
            magnet_with_taper.moved(Location((magnet_r, 0, insertion_Z)))
            .moved(Location((-pivot_x, 0, -pivot_z)))
            .moved(Rotation(0, tilt_deg, 0))
            .moved(Location((pivot_x, 0, pivot_z)))
        )
        add(insertion_cutter, mode=Mode.SUBTRACT)
        add(bore_slot, mode=Mode.SUBTRACT)
        # ── targeted fillets ──────────────────────────────────────────────────
        # 1. Frustum opening rim: non-circular edges at the insertion end face.
        frustum_lip = [
            e for e in bp.edges()
            if abs(e.center().Z - H / 2) < 0.5
            and e.geom_type != GeomType.CIRCLE
            and abs(e.center().Y) < 3.0  # exclude tangential face boundary edges
        ]
        if frustum_lip:
            try:
                fillet(frustum_lip, 0.2)
            except Exception:
                for e in frustum_lip:
                    try:
                        fillet([e], 0.2)
                    except Exception:
                        pass
        # 2. Long edges on the bore-side pocket inner face (0.1 mm).
        pocket_inner_r = R_i + inset
        inner_long = [
            e for e in bp.edges()
            if abs(math.hypot(e.center().X, e.center().Y) - pocket_inner_r) < 0.1
            and e.length > m["axial_mm"] * 0.4
        ]
        if inner_long:
            try:
                fillet(inner_long, 0.1)
            except Exception:
                for e in inner_long:
                    try:
                        fillet([e], 0.1)
                    except Exception:
                        pass

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
