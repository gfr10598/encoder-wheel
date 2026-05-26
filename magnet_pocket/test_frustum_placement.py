#!/usr/bin/env python3
"""Unit test: tracks the frustum inner-face z-position through every build step.

Expected values (config defaults)
----------------------------------
  H           = axial_mm + 2*end_face_mm = 19.0 + 2*2.0 = 23.0 mm
  z_inner     (cutter local frame)
              = H/2 - taper_in - insertion_Z
              = 11.5 - 1.5 - 4.0 = 6.0 mm
  z_inner_cell (cell frame, after .moved((magnet_r, 0, insertion_Z)))
              = z_inner + insertion_Z
              = H/2 - taper_in
              = 10.0 mm
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import yaml
from build123d import (
    Box,
    BuildPart,
    Location,
    Rotation,
    Solid,
    Wire,
    add,
    offset,
)

sys.path.insert(0, str(Path(__file__).parent))
from generate import load_config, make_magnet


# ── helpers ───────────────────────────────────────────────────────────────────

def _edges_near_z(solid: Solid, z: float, tol: float = 0.15) -> list:
    return [e for e in solid.edges() if abs(e.center().Z - z) < tol]


def _mean_z(edges) -> float:
    return sum(e.center().Z for e in edges) / len(edges)


# ── test ──────────────────────────────────────────────────────────────────────

class TestFrustumInnerFacePlacement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()

    def test_step_by_step(self):
        cfg = self.cfg
        m = cfg["magnet"]
        h = cfg["holder"]
        ins = cfg["insertion"]

        R_i         = h["ID_mm"] / 2
        H           = m["axial_mm"] + 2 * h["end_face_mm"]
        cl          = h["clearance_mm"]
        inset       = h["inset_mm"]
        taper_in    = ins["frustrum_depth_mm"]
        taper_len   = ins["taper_len_mm"]
        lead_in_cl  = ins["taper_expand_mm"]
        r0          = m["edge_radius_other_mm"]
        insertion_Z = ins["cutter_z_mm"]
        magnet_r    = R_i + m["radial_mm"] / 2 + cl / 2 + inset

        z_inner      = H / 2 - taper_in - insertion_Z   # cutter local frame
        z_outer      = z_inner + taper_len
        z_inner_cell = z_inner + insertion_Z             # = H/2 - taper_in

        print("\n── Frustum inner-face tracking ──────────────────────────────────")
        print(f"  H={H:.3f}  taper_in={taper_in:.3f}  insertion_Z={insertion_Z:.3f}")
        print(f"  z_inner (local) = {z_inner:.4f} mm")
        print(f"  z_inner (cell)  = {z_inner_cell:.4f} mm  (= H/2 - taper_in = {H/2:.3f} - {taper_in:.3f})")

        # ── Step 1: raw magnet ───────────────────────────────────────────────
        magnet = make_magnet(cfg)
        top_z = max(e.center().Z for e in magnet.edges())
        print(f"\n[1] magnet built          top edge z = {top_z:.4f}  (expect {m['axial_mm']/2:.4f})")
        self.assertAlmostEqual(top_z, m["axial_mm"] / 2, places=2,
                               msg="magnet top not at axial_mm/2")

        # ── Step 2: clearance offset ─────────────────────────────────────────
        with BuildPart() as bp_cl:
            add(magnet)
            offset(amount=cl / 2)
        magnet_cleared = bp_cl.part
        top_z_cl = max(e.center().Z for e in magnet_cleared.edges())
        expected_top_cl = m["axial_mm"] / 2 + cl / 2
        print(f"[2] offset(cl/2={cl/2:.3f})        top edge z = {top_z_cl:.4f}  (expect ≈{expected_top_cl:.4f})")
        self.assertAlmostEqual(top_z_cl, expected_top_cl, places=1,
                               msg="offset magnet top not at axial_mm/2 + cl/2")

        # ── Step 3: bisect at z_inner — confirm cut face lands exactly there ─
        cutter_slab = Box(1000, 1000, 1000).moved(Location((0, 0, z_inner + 500)))
        magnet_lower = magnet_cleared.cut(cutter_slab)
        top_faces = [f for f in magnet_lower.faces() if abs(f.center().Z - z_inner) < 0.1]
        self.assertTrue(top_faces,
                        f"No face found at z_inner={z_inner:.3f} in bisected magnet_cleared")
        cs_face_z = max(f.center().Z for f in top_faces)
        print(f"[3] bisect at z_inner={z_inner:.3f}  top face z = {cs_face_z:.4f}  (expect {z_inner:.4f})")
        self.assertAlmostEqual(cs_face_z, z_inner, places=2,
                               msg="bisect face not at z_inner")

        # ── Step 4: build loft — confirm frustum bottom face ────────────────
        cs_face = max(top_faces, key=lambda f: f.area)
        w_inner = cs_face.outer_wire()

        dx_out = m["radial_mm"] + 2 * lead_in_cl
        dy_out = m["tangential_mm"] + 2 * lead_in_cl
        r_out  = r0 + lead_in_cl
        hw, hh = dx_out / 2, dy_out / 2
        rect   = Wire.make_polygon(
            [(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)], close=True
        )
        w_outer = rect.fillet_2d(r_out, rect.vertices()).moved(Location((0, 0, z_outer)))
        taper_frustrum = Solid.make_loft([w_inner, w_outer])

        bot_faces = [f for f in taper_frustrum.faces() if abs(f.center().Z - z_inner) < 0.1]
        self.assertTrue(bot_faces, "No bottom face at z_inner in taper_frustrum")
        frust_bot_z = max(f.center().Z for f in bot_faces)
        print(f"[4] frustum lofted        bottom face z = {frust_bot_z:.4f}  (expect {z_inner:.4f})")
        self.assertAlmostEqual(frust_bot_z, z_inner, places=2,
                               msg="frustum bottom face not at z_inner")

        # ── Step 5: fuse magnet_cleared + frustum — step edges at z_inner ────
        with BuildPart() as cutter_bp:
            add(magnet_cleared)
            add(taper_frustrum)
        magnet_with_taper = cutter_bp.part

        step_edges = _edges_near_z(magnet_with_taper, z_inner)
        self.assertTrue(step_edges,
                        f"No step edges near z={z_inner:.3f} in fused cutter (magnet+frustum)")
        mean_fused = _mean_z(step_edges)
        print(f"[5] fused cutter          {len(step_edges)} step edges  mean z = {mean_fused:.4f}  (expect {z_inner:.4f})")
        self.assertAlmostEqual(mean_fused, z_inner, places=1,
                               msg="fused cutter step not at z_inner")

        # ── Step 6: move to cell frame (translation only, no tilt) ───────────
        cutter_placed = magnet_with_taper.moved(Location((magnet_r, 0, insertion_Z)))
        step_cell = _edges_near_z(cutter_placed, z_inner_cell)
        self.assertTrue(step_cell,
                        f"No step edges near z={z_inner_cell:.3f} after placement in cell frame")
        mean_cell = _mean_z(step_cell)
        print(f"[6] placed +insertion_Z   {len(step_cell)} step edges  mean z = {mean_cell:.4f}  (expect {z_inner_cell:.4f})")
        self.assertAlmostEqual(mean_cell, z_inner_cell, places=1,
                               msg="placed cutter step not at H/2 - taper_in in cell frame")

        # ── Step 7: apply tilt (same sequence as make_cell) ──────────────────
        pivot_x     = R_i + cl / 2 + inset
        pivot_z     = insertion_Z - m["axial_mm"] / 2
        face_shift  = ins["rim_target_mm"] - inset
        face_to_pivot = H / 2 - pivot_z
        tilt_deg    = math.degrees(math.atan(face_shift / face_to_pivot))

        insertion_cutter = (
            magnet_with_taper
            .moved(Location((magnet_r, 0, insertion_Z)))
            .moved(Location((-pivot_x, 0, -pivot_z)))
            .moved(Rotation(0, tilt_deg, 0))
            .moved(Location((pivot_x, 0, pivot_z)))
        )

        # After tilt the step plane is no longer flat — use a wider window.
        step_tilted = _edges_near_z(insertion_cutter, z_inner_cell, tol=0.5)
        if step_tilted:
            zs = [e.center().Z for e in step_tilted]
            zmin, zmax, zmean = min(zs), max(zs), sum(zs) / len(zs)
            print(
                f"[7] after tilt ({tilt_deg:.2f}°)    {len(step_tilted)} step edges "
                f"z ∈ [{zmin:.3f}, {zmax:.3f}]  mean={zmean:.4f}  (expect ≈{z_inner_cell:.4f})"
            )
        else:
            print(f"[7] after tilt — no step edges found near z={z_inner_cell:.3f} (tol=±0.5)")

        print(f"\n── Summary ─────────────────────────────────────────────────────")
        print(f"  Formula:  H/2 - taper_in = {H/2:.4f} - {taper_in:.4f} = {z_inner_cell:.4f} mm")
        print(f"  Measured: mean step z (cell, pre-tilt) = {mean_cell:.4f} mm")
        print(f"  Delta:    {abs(mean_cell - z_inner_cell):.4f} mm")


if __name__ == "__main__":
    unittest.main(verbosity=2)
