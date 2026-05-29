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

import argparse
import math
import sys
from pathlib import Path

import yaml
from build123d import (
    Axis,
    Box,
    BuildPart,
    Compound,
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


# ── sector-wall symmetry check ────────────────────────────────────────────────


def _radial(face: Face) -> float:
    """Distance of face centroid from the Z axis."""
    c = face.center()
    return math.hypot(c.X, c.Y)


def _sector_walls(cell: Solid) -> tuple[list[Face], list[Face]]:
    """Return (left_walls, right_walls) sorted by radial centroid distance.

    Sector boundary faces are planar and have normals lying in the XY plane
    (|normal.Z| ≈ 0).  Left walls have centroid Y < 0; right walls Y > 0.
    """
    left: list[Face] = []
    right: list[Face] = []
    for f in cell.faces():
        if f.geom_type != GeomType.PLANE:
            continue
        try:
            nz = f.normal_at(f.center()).Z
        except Exception:
            continue
        if abs(nz) > 0.05:  # end-cap or near-horizontal face — skip
            continue
        cy = f.center().Y
        if cy < -0.01:
            left.append(f)
        elif cy > 0.01:
            right.append(f)
    left.sort(key=_radial)
    right.sort(key=_radial)
    return left, right


def check_sector_symmetry(cell: Solid, cfg: dict) -> None:
    """Assert adjacent cells will mate flush.

    Step 1 — structural check
      • Each sector wall must contain the same number of face fragments k
        (2k total across both walls) and every fragment centroid must lie
        within the ring's radial bounds [R_i, R_o].

    Step 2 — geometric check on adjacent cells
      Rotates a copy of the cell by one span and compares the right wall of
      the original against the left wall of the rotated copy, using:
        • total face area
        • area-weighted centroid (XYZ)
        • area-weighted mean normal direction
      Faces within each wall group are sorted by radial centroid distance
      before comparison so the check is insensitive to fragment ordering.
    """
    h = cfg["holder"]
    R_i = h["ID_mm"] / 2
    R_o = R_i + h["thickness_mm"]
    span_deg = 360.0 / h["magnet_count"]

    left_faces, right_faces = _sector_walls(cell)

    # ── Step 1: 2k faces within ring bounds ──────────────────────────────────
    k_left, k_right = len(left_faces), len(right_faces)
    if k_left != k_right:
        raise AssertionError(
            f"Sector wall fragment counts differ: left={k_left}, right={k_right} "
            f"(expected equal k for 2k total)"
        )
    if k_left == 0:
        raise AssertionError("No sector wall faces found")
    print(f"  · sector walls: 2×{k_left} = {2*k_left} face fragments")

    for side, faces in (("left", left_faces), ("right", right_faces)):
        for i, f in enumerate(faces):
            r = _radial(f)
            if not (R_i - 0.5 <= r <= R_o + 0.5):
                raise AssertionError(
                    f"{side} wall face {i}: centroid radius {r:.3f} mm "
                    f"outside ring bounds [{R_i:.3f}, {R_o:.3f}]"
                )
        radii = [_radial(f) for f in faces]
        print(
            f"  · {side:5s} wall radii (sorted): "
            + "  ".join(f"{r:.2f}" for r in radii)
        )

    # ── Step 2: compare left wall vs right wall of cell 0 ────────────────────
    # Cell 1 = cell 0 rotated by span_deg; its left wall is cell 0's left wall
    # rotated into the same angular position as cell 0's right wall.  Mating
    # requires the two walls to be congruent.  We verify this by comparing
    # left_faces and right_faces of cell 0 directly (Y-symmetry check):
    #   • equal total area
    #   • equal centroid radii (sorted fragment-by-fragment)
    #   • normals are Y-mirror images of each other (dot of right with Y-flipped
    #     left ≈ +1)

    def _stats(faces: list[Face]) -> tuple[float, list[float], tuple]:
        total_area = sum(f.area for f in faces)
        nx_sum = sum(f.normal_at(f.center()).X * f.area for f in faces)
        ny_sum = sum(f.normal_at(f.center()).Y * f.area for f in faces)
        nz_sum = sum(f.normal_at(f.center()).Z * f.area for f in faces)
        mag = math.sqrt(nx_sum**2 + ny_sum**2 + nz_sum**2)
        radii = [_radial(f) for f in faces]  # already sorted by _sector_walls
        return total_area, radii, (nx_sum / mag, ny_sum / mag, nz_sum / mag)

    r_area, r_radii, r_nrm = _stats(right_faces)
    l_area, l_radii, l_nrm = _stats(left_faces)

    if abs(r_area - l_area) > 0.01:
        raise AssertionError(
            f"Left/right wall areas differ: left={l_area:.4f}, right={r_area:.4f} mm² "
            f"— cell is not Y-symmetric; adjacent cells will not mate flush"
        )
    for i, (lr, rr) in enumerate(zip(l_radii, r_radii)):
        if abs(lr - rr) > 0.1:
            raise AssertionError(
                f"Fragment {i} centroid radii differ: "
                f"left={lr:.3f}, right={rr:.3f} mm"
            )
    # Right normal · Y-flipped left normal should be ≈ +1 for mirror symmetry
    dot_mirror = r_nrm[0] * l_nrm[0] + r_nrm[1] * (-l_nrm[1]) + r_nrm[2] * l_nrm[2]
    if dot_mirror < 0.99:
        raise AssertionError(
            f"Wall normals not Y-mirror-symmetric: dot={dot_mirror:.4f} (expect ≈ 1)"
        )
    print(
        f"  ✓ sector walls mate: area={r_area:.4f} mm²  "
        f"radii={[f'{r:.2f}' for r in r_radii]}  "
        f"mirror-dot={dot_mirror:.4f}"
    )


# ── arc assembly ──────────────────────────────────────────────────────────────


def make_index_patch(
    cell: Solid,
    cfg: dict,
    z_center: float = 7.0,
    height_mm: float = 3.0,
    depth_mm: float = 0.4,
) -> tuple[Solid, Solid]:
    """Cut a cylindrical arc recess from the outer face of *cell*.

    The recess spans the full angular width of one cell and is *depth_mm* deep
    (radially inward from R_o).  It sits at *z_center* to stay clear of the
    ±4 mm groove.

    Returns
    -------
    cell_with_pocket : cell body with the recess subtracted
    patch            : cylindrical arc solid that fills the recess
    """
    h = cfg["holder"]
    R_o = h["ID_mm"] / 2 + h["thickness_mm"]
    total = h["magnet_count"]
    span_deg = 360.0 / total

    b_pts = [
        (R_o - depth_mm, 0.0, z_center - height_mm / 2),
        (R_o, 0.0, z_center - height_mm / 2),
        (R_o, 0.0, z_center + height_mm / 2),
        (R_o - depth_mm, 0.0, z_center + height_mm / 2),
    ]
    b_edges = [Edge.make_line(b_pts[i], b_pts[(i + 1) % 4]) for i in range(4)]
    patch = Solid.revolve(Face(Wire(b_edges)), span_deg, Axis.Z)
    patch = patch.moved(Rotation(0, 0, -span_deg / 2))

    return cell - patch, patch


def assemble_arc(
    cell: Solid, cfg: dict, n_cells: int
) -> tuple[list[Solid], list[Solid], list[Solid], list[Solid]]:
    """Place *n_cells* copies around the ring at their correct angular positions.

    Returns
    -------
    group_a : even-indexed cells (0, 2, 4, …)
    group_b : odd-indexed cells (1, 3, 5, …)
    group_c : cylindrical arc patch on the quarter-position landmark cell
    group_d : cylindrical arc patch on the half-position landmark cell
              (groups c/d non-empty only when total % 4 == 0 and n_cells ≥ total/2)

    Landmark cells stay in their even/odd group but have a cylindrical arc
    recess on their outer face; the matching patch goes into group_c or group_d.
    """
    total = cfg["holder"]["magnet_count"]
    span_deg = 360.0 / total

    # Map cell index → patch group name
    landmark_map: dict[int, str] = {}
    if total % 4 == 0 and n_cells >= total // 2:
        quarter_idx = total // 4 - 1
        half_idx = total // 2 - 1
        if quarter_idx < n_cells:
            landmark_map[quarter_idx] = "c"
        if half_idx < n_cells:
            landmark_map[half_idx] = "d"

    # Pre-build the patched cell variant once (shared geometry, rotated per use)
    cell_patched, patch_template = make_index_patch(cell, cfg)

    group_a: list[Solid] = []
    group_b: list[Solid] = []
    group_c: list[Solid] = []
    group_d: list[Solid] = []
    patch_groups: dict[str, list[Solid]] = {"c": group_c, "d": group_d}

    for i in range(n_cells):
        rot = Rotation(0, 0, i * span_deg)
        if i in landmark_map:
            body = cell_patched.moved(rot)
            patch = patch_template.moved(rot)
            if i % 2 == 0:
                body.label = f"a_{i}"
                group_a.append(body)
            else:
                body.label = f"b_{i}"
                group_b.append(body)
            pg = landmark_map[i]
            patch.label = f"{pg}_{i}"
            patch_groups[pg].append(patch)
        elif i % 2 == 0:
            placed = cell.moved(rot)
            placed.label = f"a_{i}"
            group_a.append(placed)
        else:
            placed = cell.moved(rot)
            placed.label = f"b_{i}"
            group_b.append(placed)

    return group_a, group_b, group_c, group_d


# ── cell ──────────────────────────────────────────────────────────────────────


def make_cell(cfg: dict) -> tuple[Solid, Solid, list]:
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
            4.0,  # tangential: 4 mm centred on pocket
            m["axial_mm"],  # axial: full magnet length
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
        # ── arc groove on outer face (follows ring curvature) ─────────────────
        # Floor clears the taper frustum outer edge (outer_face + lead_in_cl)
        # by groove_clearance mm.  Walls taper 30° outward so the opening is
        # wider than the floor.  Revolved 360° so it follows the arc of the ring.
        groove_clearance = 0.4
        groove_axial_mm = 8.0
        groove_tilt_deg = 30.0
        groove_floor_r = outer_face + lead_in_cl + groove_clearance
        groove_depth = R_o - groove_floor_r
        if groove_depth > 0:
            extra = 5.0  # extends past R_o to break through outer face
            taper = groove_depth * math.tan(math.radians(groove_tilt_deg))
            half_bot = groove_axial_mm / 2
            half_top = half_bot + taper
            # Trapezoid profile in the XZ plane (y=0); revolve 360° → ring cutter
            g_pts = [
                (groove_floor_r, 0, -half_bot),
                (R_o + extra, 0, -half_top),
                (R_o + extra, 0, +half_top),
                (groove_floor_r, 0, +half_bot),
            ]
            g_edges = [Edge.make_line(g_pts[i], g_pts[(i + 1) % 4]) for i in range(4)]
            groove_ring = Solid.revolve(Face(Wire(g_edges)), 360.0, Axis.Z)
            add(groove_ring, mode=Mode.SUBTRACT)
            # Fillet bottom edges (floor-wall junction) and top edges (opening rim)
            groove_fillet_r = 0.5
            groove_btm = [
                e
                for e in bp.edges()
                if abs(abs(e.center().Z) - half_bot) < 0.2
                and abs(math.hypot(e.center().X, e.center().Y) - groove_floor_r) < 0.5
                and e.geom_type == GeomType.CIRCLE
            ]
            groove_top = [
                e
                for e in bp.edges()
                if 3.5 < abs(e.center().Z) < half_top + 1.0
                and abs(math.hypot(e.center().X, e.center().Y) - R_o) < 0.5
                and e.geom_type == GeomType.CIRCLE
            ]
            for edge_list in (groove_btm, groove_top):
                if edge_list:
                    try:
                        fillet(edge_list, groove_fillet_r)
                    except Exception:
                        for e in edge_list:
                            try:
                                fillet([e], groove_fillet_r)
                            except Exception:
                                pass
        # ── press hole: 3 mm radial access through the OD wall ───────────────
        # A pin inserted from outside presses the magnet radially inward onto
        # the bore.  Hole centre is at the magnet's top face so the pin bears
        # on the magnet face.  Placed at Y=0 (centred on the pocket).
        ph_d = 3.0
        ph_r = ph_d / 2
        ph_z = m["axial_mm"] / 2 - ph_r - 1.0  # 1 mm below magnet top face
        ph_length = R_o - outer_face + ph_r + 2.0  # through OD wall + margin
        press_hole = (
            Solid.make_cylinder(ph_r, ph_length)
            .moved(Rotation(0, 90, 0))           # cylinder now along +X (radial)
            .moved(Location((outer_face - ph_r, 0, ph_z)))
        )
        add(press_hole, mode=Mode.SUBTRACT)

        # ── retention beads: axial cylindrical ridges on the pocket tangential walls ──
        # Short cylinders (2 mm, axis along Z) centred at the pocket tangential wall,
        # half-embedded in the wall, half proud into the void.
        # Top face sits at the magnet's seated upper edge so the magnet snaps past
        # and the bead engages the rounded top corner when fully inserted.
        bead_r = 0.15        # mm radius
        bead_len = 2.0       # mm axial height
        bead_z_start = m["axial_mm"] / 2 - bead_len + 0.1  # top face 0.1 mm above magnet top
        pocket_half_tan = m["tangential_mm"] / 2 + cl / 2
        # Shift bead radially outward so its surface just touches (zero interference)
        # the magnet's outer-tangential axial edge fillet when the magnet is seated.
        # The fillet centre is at (outer_face - r0, tan_face - r0); we need
        # bead_centre distance from fillet_centre == bead_r + r0.
        # With Y fixed at pocket_half_tan:  delta_x = sqrt((bead_r+r0)^2 - (cl/2+r0)^2) - r0
        r0 = m["edge_radius_other_mm"]
        bead_x = (magnet_r + m["radial_mm"] / 2
                  + math.sqrt((bead_r + r0) ** 2 - (cl / 2 + r0) ** 2) - r0)
        for sign in (+1.0, -1.0):
            add(Solid.make_cylinder(bead_r, bead_len)   # axis already along Z
                .moved(Location((bead_x, sign * pocket_half_tan, bead_z_start))))

        # ── targeted fillets ──────────────────────────────────────────────────
        # 1. Frustum opening rim: non-circular edges at the insertion end face.
        frustum_lip = [
            e
            for e in bp.edges()
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
            e
            for e in bp.edges()
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
        # 3. Press-hole entry rim on the OD surface only — the inner rim sits on
        #    the angled insertion-cutter face at this Z and cannot be cleanly filleted.
        ph_fillet = 0.2
        press_rims = [
            e
            for e in bp.edges()
            if abs(e.center().Z - ph_z) < ph_r + 0.5
            and abs(e.center().Y) < ph_r + 0.5
            and abs(math.hypot(e.center().X, e.center().Y) - R_o) < 0.5
        ]
        if press_rims:
            try:
                fillet(press_rims, ph_fillet)
            except Exception:
                for e in press_rims:
                    try:
                        fillet([e], ph_fillet)
                    except Exception:
                        pass

    return bp.part, positioned_magnet


# ── 3MF export ───────────────────────────────────────────────────────────────

_GROUP_META: dict[str, tuple[str, tuple[int, int, int]]] = {
    "a": ("North", (230, 230, 230)),
    "b": ("South", (30, 30, 30)),
    "c": ("Index_Q", (220, 50, 50)),
    "d": ("Index_H", (50, 80, 220)),
}


def _export_3mf(groups: dict[str, list[Solid]], stem: str, out_dir: Path) -> None:
    """Export all non-empty groups as a single multi-material 3MF file."""
    import lib3mf  # type: ignore[import]

    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)

    mat_group = model.AddBaseMaterialGroup()
    mat_rid = mat_group.GetUniqueResourceID()

    mat_mid: dict[str, int] = {}
    for key, (label, (r, g, b)) in _GROUP_META.items():
        if groups.get(key):
            mat_mid[key] = mat_group.AddMaterial(
                label, lib3mf.Color(Red=r, Green=g, Blue=b, Alpha=255)
            )

    for key, grp in groups.items():
        if not grp:
            continue
        label = _GROUP_META[key][0]
        compound = Compound(children=grp)
        raw_verts, raw_tris = compound.tessellate(0.05, 0.5)

        positions: list = []
        for v in raw_verts:
            p = lib3mf.Position()
            p.Coordinates[0] = float(v.X)
            p.Coordinates[1] = float(v.Y)
            p.Coordinates[2] = float(v.Z)
            positions.append(p)

        triangles: list = []
        for t in raw_tris:
            tri = lib3mf.Triangle()
            tri.Indices[0] = t[0]
            tri.Indices[1] = t[1]
            tri.Indices[2] = t[2]
            triangles.append(tri)

        mesh = model.AddMeshObject()
        mesh.SetName(label)
        mesh.SetGeometry(positions, triangles)
        mesh.SetObjectLevelProperty(mat_rid, mat_mid[key])
        model.AddBuildItem(mesh, wrapper.GetIdentityTransform())

    out_path = out_dir / f"{stem}.3mf"
    writer = model.QueryWriter("3mf")
    writer.WriteToFile(str(out_path))
    print(f"Exported → {out_path}")


def _prime_factors(n: int) -> list[int]:
    """Return the prime factors of n in ascending order, with repetition."""
    factors: list[int] = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


def _fuse_arc_doubling(cell: Solid, cfg: dict, n_cells: int) -> Solid:
    """Build an arc of n_cells via factored multiply-and-fuse.

    Factors n_cells into primes, then scales the accumulated arc by each factor
    in turn using a double-and-add chain (binary exponentiation for addition).
    This gives the minimum number of fuse operations for each factor, e.g.:

      n=5  (prime)   → ×5 via double→double→+1  = 3 fuses  ("2×2+1")
      n=9  = 3×3     → ×3 (2 fuses) then ×3 again  = 4 fuses
      n=18 = 2×3×3   → ×2 (1) + ×3 (2) + ×3 (2)    = 5 fuses
      n=25 = 5×5     → ×5 (3 fuses) then ×5 again   = 6 fuses

    Because we build the exact count, no surplus cut is ever needed.
    Each fuse is validated immediately; raises ValueError on disconnected bodies.
    No landmark patches or North/South group distinctions are applied.
    """
    if n_cells == 1:
        return cell

    total = cfg["holder"]["magnet_count"]
    span_deg = 360.0 / total

    factors = _prime_factors(n_cells)
    print(f"  Factorization: {n_cells} = " + " × ".join(str(f) for f in factors))

    current = cell
    count = 1  # cells in current

    for f in factors:
        # double-and-add: build f copies of current placed at consecutive positions
        # n_built tracks how many count-wide copies we've accumulated so far
        n_built = 1
        result = current

        for bit in range(f.bit_length() - 2, -1, -1):
            # Double: place result adjacent to itself
            copy = result.moved(Rotation(0, 0, n_built * count * span_deg))
            result = result.fuse(copy)
            n_built *= 2
            n_b = len(result.solids())
            if n_b != 1:
                raise ValueError(
                    f"×{f}: double to {n_built} cells — fuse produced {n_b} bodies; "
                    "check for a gap between adjacent cells"
                )
            # Add one original if this bit of f is set
            if (f >> bit) & 1:
                copy = current.moved(Rotation(0, 0, n_built * count * span_deg))
                result = result.fuse(copy)
                n_built += 1
                n_b = len(result.solids())
                if n_b != 1:
                    raise ValueError(
                        f"×{f}: +1 to {n_built} cells — fuse produced {n_b} bodies; "
                        "check for a gap between adjacent cells"
                    )

        current = result
        count *= f
        print(f"  ×{f}: {count} cells — 1 solid OK")

    return current


def _fuse_all(solids: list[Solid]) -> Solid:
    """Boolean-union all solids into one using a tree reduction.

    Pairs up solids at each level so each individual operation stays small,
    giving O(log n) depth instead of O(n).  Warns if the result contains more
    than one disconnected body, which indicates gaps between adjacent cells.
    """
    if not solids:
        raise ValueError("_fuse_all: no solids provided")
    layer = list(solids)
    n_total = len(layer)
    print(f"  Fusing {n_total} solids (tree reduction)...")
    level = 0
    while len(layer) > 1:
        next_layer = []
        for i in range(0, len(layer) - 1, 2):
            fused = layer[i].fuse(layer[i + 1])
            n_bodies = len(fused.solids())
            if n_bodies != 1:
                raise ValueError(
                    f"  level {level} pair {i//2}: fuse produced {n_bodies} "
                    "disconnected bodies — check for a gap between adjacent cells"
                )
            next_layer.append(fused)
        if len(layer) % 2 == 1:
            next_layer.append(layer[-1])
        level += 1
        layer = next_layer
    result = layer[0]
    print(f"  Fuse OK — 1 solid body ({level} levels)")
    return result


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate magnet pocket cells")
    parser.add_argument(
        "--cells",
        type=int,
        default=None,
        metavar="N",
        help="assemble N adjacent cells into an arc (exports arc<N>_<total>.step)",
    )
    parser.add_argument(
        "--fuse-all",
        action="store_true",
        help="boolean-union all cells into one solid and export an extra *_fused.step",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="write STEP files to output/ (default: show in OCP viewer only)",
    )
    args = parser.parse_args()

    cfg = load_config()

    sys.path.insert(0, str(Path(__file__).parent))
    from validate_config import validate

    failures = validate(cfg)
    if failures:
        print(f"\nConfig validation failed: {', '.join(failures)}")
        sys.exit(1)

    total = cfg["holder"]["magnet_count"]
    out_dir = Path(__file__).parent / "output"
    out_dir.mkdir(exist_ok=True)

    print("\nBuilding cell...")
    cell, magnet = make_cell(cfg)

    if args.cells is not None:
        n = args.cells
        if not (1 <= n <= total):
            print(f"--cells must be 1–{total}; got {n}")
            sys.exit(1)

        print("Checking sector symmetry...")
        check_sector_symmetry(cell, cfg)

        stem = f"arc_ID{cfg['holder']['ID_mm']:g}mm_{n}_{total}"

        if args.fuse_all:
            print(f"Building fused arc {n}/{total} via doubling...")
            fused = _fuse_arc_doubling(cell, cfg, n)

            try:
                from ocp_vscode import Camera, show, set_port  # type: ignore[import]

                set_port(3939)
                show(fused, names=["fused_arc"], reset_camera=Camera.CENTER)
            except ImportError:
                pass

            if args.export:
                fused_stem = stem + "_fused"
                _export_3mf({"a": [fused]}, fused_stem, out_dir)
                fused_path = out_dir / f"{fused_stem}.step"
                export_step(fused, str(fused_path))
                print(f"Exported → {fused_path}")

        else:
            print(f"Assembling arc {n}/{total}...")
            group_a, group_b, group_c, group_d = assemble_arc(cell, cfg, n)
            groups = {"a": group_a, "b": group_b, "c": group_c, "d": group_d}
            for name, grp in groups.items():
                n_grp = len(grp)
                print(f"  group {name}: {n_grp} {'cell' if n_grp == 1 else 'cells'}")

            try:
                from ocp_vscode import Camera, show, set_port  # type: ignore[import]

                set_port(3939)
                show_objs = []
                show_names = []
                show_colors = []
                ocp_labels = {"a": "North", "b": "South", "c": "Index_Q", "d": "Index_H"}
                for grp_name, grp_solids, color, alpha in [
                    ("a", group_a, "#ffffff", 0.95),
                    ("b", group_b, "#000000", 1.0),
                    ("c", group_c, "#ff0000", 1.0),
                    ("d", group_d, "#0000ff", 1.0),
                ]:
                    if grp_solids:
                        show_objs.append(Compound(children=grp_solids))
                        show_names.append(ocp_labels[grp_name])
                        show_colors.append(color)
                show(
                    *show_objs,
                    names=show_names,
                    colors=show_colors,
                    alphas=[0.95 if n == "group_a" else 1.0 for n in show_names],
                    reset_camera=Camera.CENTER,
                )
            except ImportError:
                pass

            if args.export:
                _export_3mf(groups, stem, out_dir)

    else:
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

        if args.export:
            id_mm = cfg["holder"]["ID_mm"]
            stem = f"ID{id_mm:g}mm"
            export_step(cell, str(out_dir / f"cell_{stem}.step"))
            export_step(magnet, str(out_dir / f"magnet_{stem}.step"))
            print(f"Exported → {out_dir}/")


if __name__ == "__main__":
    main()
