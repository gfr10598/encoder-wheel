import unittest

from scripts.generate_multipart_ring import (
    MIN_OPEN_HOLE_DIAMETER_MM,
    MultipartEncoderScadGenerator,
    MultipartEncoderSpec,
    MultipartOutputValidator,
)


class MultipartEncoderSpecTests(unittest.TestCase):
    def test_default_spec_matches_issue_constraints(self):
        spec = MultipartEncoderSpec()
        self.assertEqual(spec.n_magnets, 90)
        self.assertGreaterEqual(spec.open_hole_diameter_mm, MIN_OPEN_HOLE_DIAMETER_MM)
        self.assertAlmostEqual(spec.steel_inner_diameter_mm, 152.4)
        self.assertAlmostEqual(spec.steel_outer_diameter_mm, 203.2)

    def test_open_hole_must_be_at_least_four_inches(self):
        with self.assertRaises(ValueError):
            MultipartEncoderSpec(open_hole_diameter_mm=100.0)

    def test_rejects_magnet_width_larger_than_pitch(self):
        with self.assertRaises(ValueError):
            MultipartEncoderSpec(n_magnets=200, magnet_width_mm=5.0)


class MultipartScadOutputTests(unittest.TestCase):
    def test_generated_scad_contains_required_modules(self):
        spec = MultipartEncoderSpec()
        scad = MultipartEncoderScadGenerator(spec).generate()
        MultipartOutputValidator.validate_scad(scad, spec)
        self.assertIn("module u_mount_plate()", scad)
        self.assertIn("gap_bridge_plate(180);", scad)

    def test_validator_rejects_missing_tokens(self):
        spec = MultipartEncoderSpec()
        with self.assertRaises(ValueError):
            MultipartOutputValidator.validate_scad("module ring_segment() {}", spec)


if __name__ == "__main__":
    unittest.main()
