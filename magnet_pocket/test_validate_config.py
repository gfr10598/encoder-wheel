"""Unit tests for magnet_pocket/validate_config.py"""

import copy
import math
import unittest

from validate_config import validate, check_required_keys

# A fully consistent base config that should pass all checks.
# ID=101.6 mm matches the cyl26 design (26 magnets, 4-in bore).
# W_i = pi * 101.6 / 26 = 12.28 mm; available for comb = W_i - tangential(10) = 2.28 mm.
# Thin comb (tooth=0.7, wall=0.3) keeps V4/V14 comfortable; snap=0.2 satisfies V7.
BASE_CFG = {
    "magnet": {
        "radial_mm": 5.0,
        "tangential_mm": 10.0,
        "axial_mm": 20.0,
        "edge_radius_axial_mm": 0.5,
        "edge_radius_other_mm": 0.2,
    },
    "holder": {
        "material": "PETG",
        "magnet_count": 26,
        "ID_mm": 101.6,
        "thickness_mm": 8.0,
        "end_face_mm": 3.0,
        "clearance_mm": 0.1,
        "bore_snap_mm": 0.15,
        "fillet_radius_mm": 0.5,  # cylinder edge radius.
    },
    "comb": {
        "count": 3,
        "thickness_mm": 0.7,  # thin to fit inside W_i; snap limit = 0.35 mm
        "axial_gap": 0.5,
        "clearance_mm": 0.1,
        "snap_overhang_mm": 0.2,
        "snap_type": "full",
    },
}


def _cfg(**overrides):
    """Return a deep copy of BASE_CFG with nested key overrides applied.
    Pass overrides as section__key=value, e.g. magnet__radial_mm=99.
    """
    cfg = copy.deepcopy(BASE_CFG)
    for dotkey, val in overrides.items():
        section, key = dotkey.split("__", 1)
        cfg[section][key] = val
    return cfg


class TestBaseConfigPasses(unittest.TestCase):
    def test_base_passes_all(self):
        failures = validate(BASE_CFG)
        self.assertEqual(failures, [], f"Base config should pass; failed: {failures}")


class TestRequiredKeys(unittest.TestCase):
    def test_missing_section(self):
        cfg = copy.deepcopy(BASE_CFG)
        del cfg["comb"]
        missing = check_required_keys(cfg)
        self.assertIn("comb", missing)

    def test_missing_key(self):
        cfg = copy.deepcopy(BASE_CFG)
        del cfg["holder"]["bore_snap_mm"]
        missing = check_required_keys(cfg)
        self.assertIn("holder.bore_snap_mm", missing)

    def test_malformed_config_returns_keys_failure(self):
        cfg = copy.deepcopy(BASE_CFG)
        del cfg["magnet"]["radial_mm"]
        failures = validate(cfg)
        self.assertIn("KEYS", failures)


class TestV1EvenCount(unittest.TestCase):
    def test_odd_count_fails(self):
        self.assertIn("V1", validate(_cfg(holder__magnet_count=25)))

    def test_even_count_passes(self):
        self.assertNotIn("V1", validate(_cfg(holder__magnet_count=26)))


class TestV2RadialFit(unittest.TestCase):
    def test_magnet_too_thick_fails(self):
        self.assertIn("V2", validate(_cfg(magnet__radial_mm=8.0)))  # 8.0 + 0.1 >= 8.0

    def test_magnet_fits_passes(self):
        self.assertNotIn("V2", validate(_cfg(magnet__radial_mm=5.0)))


class TestV3OuterWallPrintable(unittest.TestCase):
    def test_thin_outer_wall_fails(self):
        # outer_wall = 8.0 - 7.5 - 0.1 = 0.4 < 0.8
        self.assertIn("V3", validate(_cfg(magnet__radial_mm=7.5)))

    def test_adequate_outer_wall_passes(self):
        # outer_wall = 8.0 - 5.0 - 0.1 = 2.9 >= 0.8
        self.assertNotIn("V3", validate(_cfg(magnet__radial_mm=5.0)))


class TestV4TangentialFit(unittest.TestCase):
    def test_magnet_too_wide_fails(self):
        # Make magnet very wide so it can't fit in the arc
        self.assertIn("V4", validate(_cfg(magnet__tangential_mm=20.0)))

    def test_narrow_magnet_passes(self):
        self.assertNotIn("V4", validate(BASE_CFG))


class TestV5CombToothWidth(unittest.TestCase):
    def test_too_many_teeth_fails(self):
        # H=24, count=100 → pitch=0.12, tooth_width=0.12-0.5 < 0
        self.assertIn("V5", validate(_cfg(comb__count=100)))

    def test_few_teeth_passes(self):
        self.assertNotIn("V5", validate(_cfg(comb__count=3)))


class TestV6CombToothDepth(unittest.TestCase):
    def test_depth_less_than_clearance_fails(self):
        self.assertIn("V6", validate(_cfg(comb__thickness_mm=0.05)))

    def test_depth_greater_than_clearance_passes(self):
        self.assertNotIn("V6", validate(_cfg(comb__thickness_mm=2.0)))


class TestV7SnapHalfTooth(unittest.TestCase):
    def test_snap_too_large_fails(self):
        self.assertIn("V7", validate(_cfg(comb__snap_overhang_mm=1.5)))  # > 0.7/2

    def test_snap_at_limit_passes(self):
        # Explicitly set tooth=2.0 so the limit is exactly 1.0
        self.assertNotIn(
            "V7", validate(_cfg(comb__thickness_mm=2.0, comb__snap_overhang_mm=1.0))
        )


class TestV8BoreSnap(unittest.TestCase):
    def test_snap_exceeds_edge_radius_fails(self):
        self.assertIn(
            "V8", validate(_cfg(holder__bore_snap_mm=0.5))
        )  # > edge_radius 0.2

    def test_snap_within_edge_radius_passes(self):
        self.assertNotIn("V8", validate(_cfg(holder__bore_snap_mm=0.15)))


class TestV9AxialFillet(unittest.TestCase):
    def test_fillet_too_large_fails(self):
        # min(tangential=10, radial=5)/2 = 2.5; use 3.0
        self.assertIn("V9", validate(_cfg(magnet__edge_radius_axial_mm=3.0)))

    def test_fillet_within_limit_passes(self):
        self.assertNotIn("V9", validate(_cfg(magnet__edge_radius_axial_mm=0.5)))


class TestV10OtherFillet(unittest.TestCase):
    def test_fillet_too_large_fails(self):
        # min(axial=20, tangential=10)/2 = 5.0; use 6.0
        self.assertIn("V10", validate(_cfg(magnet__edge_radius_other_mm=6.0)))

    def test_fillet_within_limit_passes(self):
        # radial_mm=5 would give min/2=2.5 if wrongly included; tangential=10 gives 5.0
        self.assertNotIn("V10", validate(_cfg(magnet__edge_radius_other_mm=0.2)))

    def test_fillet_limit_ignores_radial(self):
        # With radial=1mm, old (buggy) limit would be min(20,10,1)/2=0.5
        # Correct limit is min(20,10)/2=5.0 — a value of 1.0 should still pass
        self.assertNotIn(
            "V10",
            validate(_cfg(magnet__radial_mm=1.0, magnet__edge_radius_other_mm=0.2)),
        )


class TestV13SnapType(unittest.TestCase):
    def test_invalid_snap_type_fails(self):
        self.assertIn("V13", validate(_cfg(comb__snap_type="none")))

    def test_valid_snap_types_pass(self):
        for t in ("full", "edges", "corners"):
            with self.subTest(snap_type=t):
                self.assertNotIn("V13", validate(_cfg(comb__snap_type=t)))


class TestV14SnapDeflectionClearsAdjacent(unittest.TestCase):
    # Base config: W_i = pi*101.6/26 = 12.28 mm, magnet.tangential = 10 mm
    # available = 2.28 mm;  V14 fails when tooth(0.7) + snap + clearance(0.1) > 2.28
    # i.e. snap > 1.48 mm

    def test_large_snap_overhang_fails(self):
        self.assertIn("V14", validate(_cfg(comb__snap_overhang_mm=1.5)))

    def test_small_snap_overhang_passes(self):
        self.assertNotIn("V14", validate(_cfg(comb__snap_overhang_mm=0.2)))

    def test_v4_passes_while_v14_fails(self):
        # V4 doesn't include snap_overhang; V14 does.
        # With snap=1.5: V4 still passes (snap not in V4 formula),
        # but V14 fails because tooth(0.7) + snap(1.5) + clearance(0.1) = 2.3 > available(2.28).
        cfg = _cfg(comb__snap_overhang_mm=1.5)
        self.assertNotIn("V4", validate(cfg))
        self.assertIn("V14", validate(cfg))


if __name__ == "__main__":
    unittest.main(verbosity=2)
