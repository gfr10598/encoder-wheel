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


def make_magnet(cfg: dict) -> Solid:
    """Filleted magnet box centred at origin.  Radial=+X, tangential=Y, axial=Z.

    This is the reference body used for visualisation and pocket sizing.
    Call .moved() to position it in the ring.
    """
    m = cfg["magnet"]
    with BuildPart() as bp:
        Box(m["radial_mm"], m["tangential_mm"], m["axial_mm"])
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
    # Inner face of magnet flush with bore surface → centre at R_i + radial/2
    magnet_r = R_i + m["radial_mm"] / 2
    positioned_magnet = magnet.moved(Location((magnet_r, 0, 0)))

    # ── pocket = positioned magnet expanded by clearance ─────────────────────
    with BuildPart() as pocket_bp:
        add(positioned_magnet)
        offset(amount=cl)
    pocket = pocket_bp.part

    # ── comb slot cutters ─────────────────────────────────────────────────────
    # Comb occupies the magnet axial span with 2×edge_radius padding each end.
    # 2N tooth positions alternate L/R across that span.  Cut the N positions
    # belonging to the adjacent cell on each face.
    c = cfg["comb"]
    N = c["count"]
    r_pad = 2 * m["edge_radius_other_mm"]
    comb_span = m["axial_mm"] - 2 * r_pad  # axial extent of comb zone
    q = comb_span / (2 * N)  # pitch per tooth in combined array
    slot_h = (q - c["axial_gap"]) + 2 * c["axial_gap"]  # = q + axial_gap
    R_slot = R_i + m["radial_mm"]  # from z-axis to pocket floor

    # 2N grid centres from -comb_span/2 to +comb_span/2, step q:
    #   slot k (0-indexed): z = -comb_span/2 + (k + 0.5)*q
    # Left face owns even slots (k=0,2,...); cut the odd slots for adj. cell.
    cut_z_left = [-comb_span / 2 + (2 * k + 1.5) * q for k in range(N)]
    # Right face owns odd slots (k=1,3,...); cut the even slots for adj. cell.
    cut_z_right = [-comb_span / 2 + (2 * k + 0.5) * q for k in range(N)]

    def _slot_wedge(
        slot_z: float, rot_deg: float, height: float | None = None
    ) -> Solid:
        h_cut = height if height is not None else slot_h
        xz_pts = [
            (0.0, slot_z - h_cut / 2),
            (R_slot, slot_z - h_cut / 2),
            (R_slot, slot_z + h_cut / 2),
            (0.0, slot_z + h_cut / 2),
        ]
        pts_3d = [(x, 0.0, z) for x, z in xz_pts]
        n = len(pts_3d)
        edges = [Edge.make_line(pts_3d[i], pts_3d[(i + 1) % n]) for i in range(n)]
        # Revolve spans [0, span_deg]; rotate so it straddles the target face.
        # Left face is at +span_deg/2 → rot=0 centres wedge at span_deg/2.
        # Right face is at -span_deg/2 → rot=-span_deg centres wedge there.
        wedge = Solid.revolve(Face(Wire(edges)), span_deg, Axis.Z)
        return wedge.moved(Rotation(0, 0, rot_deg))

    # End-gap slices: free the outermost tooth on each face from the solid end wall.
    end_gap_zs = [
        -(comb_span / 2 + c["axial_gap"] / 2),
        +(comb_span / 2 + c["axial_gap"] / 2),
    ]

    slot_cutters = (
        [_slot_wedge(z, 0.0) for z in cut_z_left]
        + [_slot_wedge(z, -span_deg) for z in cut_z_right]
        + [
            _slot_wedge(z, rot, height=c["axial_gap"])
            for z in end_gap_zs
            for rot in [0.0, -span_deg]
        ]
    )

    # ── sector with filleted end arcs, then pocket and slots subtracted ───────
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
        for cutter in slot_cutters:
            add(cutter, mode=Mode.SUBTRACT)
        # ── snap hook trim: plain box centred at bore face, shrunk by snap ──────
        snap = c["snap_overhang_mm"]
        snap_cutter = Box(
            m["radial_mm"],
            m["tangential_mm"] - 2 * snap,
            m["axial_mm"],
            mode=Mode.PRIVATE,
        ).moved(Location((R_i, 0, 0)))
        add(snap_cutter, mode=Mode.SUBTRACT)

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
        show(
            cell,
            magnet,
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
