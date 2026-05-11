#!/usr/bin/env python3
"""Generate an OpenSCAD multipart encoder-ring assembly for bell gudgeon installs."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass


MM_PER_INCH = 25.4
MIN_OPEN_HOLE_DIAMETER_MM = 4.0 * MM_PER_INCH
MAX_PRINTER_RADIUS_MM = 10.0 * MM_PER_INCH


@dataclass(frozen=True)
class MultipartEncoderSpec:
    """Validated design inputs for the multipart ring assembly."""

    n_magnets: int = 90
    magnet_width_mm: float = 5.0
    magnet_length_mm: float = 20.0
    magnet_thickness_mm: float = 2.0
    steel_inner_diameter_mm: float = 6.0 * MM_PER_INCH
    steel_outer_diameter_mm: float = 8.0 * MM_PER_INCH
    open_hole_diameter_mm: float = MIN_OPEN_HOLE_DIAMETER_MM
    ring_thickness_mm: float = 6.0
    assembly_gap_mm: float = 1.0
    mount_plate_thickness_mm: float = 6.0
    mount_plate_arc_deg: float = 250.0
    output_file: str = "multipart_encoder_ring.scad"

    def __post_init__(self) -> None:
        if self.n_magnets < 2 or self.n_magnets % 2:
            raise ValueError("n_magnets must be an even integer >= 2")
        if self.magnet_width_mm <= 0 or self.magnet_length_mm <= 0 or self.magnet_thickness_mm <= 0:
            raise ValueError("magnet dimensions must be positive")
        if self.steel_inner_diameter_mm <= 0 or self.steel_outer_diameter_mm <= 0:
            raise ValueError("steel ring diameters must be positive")
        if self.steel_outer_diameter_mm <= self.steel_inner_diameter_mm:
            raise ValueError("steel_outer_diameter_mm must be larger than steel_inner_diameter_mm")
        if self.open_hole_diameter_mm < MIN_OPEN_HOLE_DIAMETER_MM:
            raise ValueError("open_hole_diameter_mm must be at least 4 inches (101.6 mm)")
        if self.open_hole_diameter_mm > self.steel_inner_diameter_mm:
            raise ValueError("open_hole_diameter_mm must fit inside the steel ring inner diameter")
        if self.ring_outer_radius_mm > MAX_PRINTER_RADIUS_MM:
            raise ValueError("ring outer radius exceeds 10 inch Bambu-printer radius limit")
        if self.assembly_gap_mm <= 0:
            raise ValueError("assembly_gap_mm must be positive")
        if self.ring_thickness_mm <= 0 or self.mount_plate_thickness_mm <= 0:
            raise ValueError("plate/ring thickness values must be positive")
        if not (180.0 <= self.mount_plate_arc_deg < 360.0):
            raise ValueError("mount_plate_arc_deg must be in [180, 360)")
        if self.magnet_pitch_mm <= self.magnet_width_mm:
            raise ValueError("magnets do not fit: magnet_width_mm must be smaller than tangential pitch")

    @property
    def ring_inner_radius_mm(self) -> float:
        return self.steel_inner_diameter_mm / 2.0

    @property
    def ring_outer_radius_mm(self) -> float:
        return self.steel_outer_diameter_mm / 2.0

    @property
    def mean_ring_radius_mm(self) -> float:
        return (self.ring_inner_radius_mm + self.ring_outer_radius_mm) / 2.0

    @property
    def magnet_pitch_mm(self) -> float:
        return (2.0 * math.pi * self.ring_inner_radius_mm) / self.n_magnets

    @property
    def assembly_gap_deg(self) -> float:
        return math.degrees(self.assembly_gap_mm / self.mean_ring_radius_mm)


class MultipartOutputValidator:
    """Validates generated output text."""

    REQUIRED_SCAD_TOKENS = (
        "module ring_segment",
        "module primary_half_ring",
        "module secondary_half_ring",
        "module gap_bridge_plate",
        "module u_mount_plate",
        "module assembly_layout",
    )

    @classmethod
    def validate_scad(cls, scad: str, spec: MultipartEncoderSpec) -> None:
        for token in cls.REQUIRED_SCAD_TOKENS:
            if token not in scad:
                raise ValueError(f"Generated SCAD is missing required token: {token}")
        if f"n_magnets           = {spec.n_magnets};" not in scad:
            raise ValueError("Generated SCAD does not include configured magnet count")
        if "set_screw_hole" not in scad or "lock_screw_hole" not in scad:
            raise ValueError("Generated SCAD is missing set/lock screw features")


class MultipartEncoderScadGenerator:
    """Build OpenSCAD content for a 4-piece multipart ring + U-mount plate."""

    def __init__(self, spec: MultipartEncoderSpec) -> None:
        self.spec = spec

    def _magnet_indices_for_segment(self, start_deg: float, sweep_deg: float) -> list[int]:
        start = start_deg % 360.0
        end = (start + sweep_deg) % 360.0
        indices: list[int] = []
        for i in range(self.spec.n_magnets):
            ang = (360.0 * i) / self.spec.n_magnets
            if start < end:
                in_range = start <= ang <= end
            else:
                in_range = ang >= start or ang <= end
            if in_range:
                indices.append(i)
        return indices

    def generate(self) -> str:
        s = self.spec
        seg_sweep = 180.0 - s.assembly_gap_deg
        primary_start = s.assembly_gap_deg / 2.0
        secondary_start = 90.0 + s.assembly_gap_deg / 2.0
        magnet_r = s.ring_inner_radius_mm + 1.0
        mount_plate_magnet_count = max(1, round(s.n_magnets * (s.mount_plate_arc_deg / 360.0)))
        mount_step = s.mount_plate_arc_deg / mount_plate_magnet_count
        mount_start = -s.mount_plate_arc_deg / 2.0
        primary_indices = self._magnet_indices_for_segment(primary_start, seg_sweep)
        secondary_indices = self._magnet_indices_for_segment(secondary_start, seg_sweep)

        lines = [
            "// =============================================================================",
            "// Multipart Encoder Ring (bell gudgeon install)",
            "// Generated by generate_multipart_ring.py — do not edit by hand.",
            "// =============================================================================",
            f"n_magnets           = {s.n_magnets};",
            f"magnet_width        = {s.magnet_width_mm:.3f};",
            f"magnet_length       = {s.magnet_length_mm:.3f};",
            f"magnet_thickness    = {s.magnet_thickness_mm:.3f};",
            f"ring_inner_radius   = {s.ring_inner_radius_mm:.3f};",
            f"ring_outer_radius   = {s.ring_outer_radius_mm:.3f};",
            f"ring_thickness      = {s.ring_thickness_mm:.3f};",
            f"assembly_gap_deg    = {s.assembly_gap_deg:.5f};",
            f"open_hole_radius    = {s.open_hole_diameter_mm / 2.0:.3f};",
            f"mount_plate_thick   = {s.mount_plate_thickness_mm:.3f};",
            "",
            "module ring_segment(start_angle, sweep_angle, z0, h, r_in, r_out) {",
            "    translate([0, 0, z0])",
            "        rotate([0, 0, start_angle])",
            "            rotate_extrude(angle = sweep_angle, $fn = 320)",
            "                translate([r_in, 0, 0])",
            "                    square([r_out - r_in, h]);",
            "}",
            "",
            "module magnet_pocket(r0, z0) {",
            "    translate([-magnet_width/2, r0, z0]) cube([magnet_width, magnet_length, magnet_thickness + 0.2]);",
            "}",
            "",
            "module seam_bridge_lug(angle_deg) {",
            "    rotate([0, 0, angle_deg])",
            "        translate([ring_outer_radius - 6.0, -4.0, -1.5]) cube([6.0, 8.0, 1.5]);",
            "}",
            "",
            "module primary_half_ring(start_angle) {",
            "    difference() {",
            f"        ring_segment(start_angle, {seg_sweep:.5f}, 0, ring_thickness, ring_inner_radius, ring_outer_radius);",
            "        for (i = [0 : n_magnets - 1]) {",
            "            rotate([0, 0, i * (360 / n_magnets)]) magnet_pocket(ring_inner_radius + 1.0, ring_thickness - magnet_thickness);",
            "        }",
            "    }",
            "    seam_bridge_lug(start_angle);",
            f"    seam_bridge_lug(start_angle + {seg_sweep:.5f});",
            "}",
            "",
            "module secondary_half_ring(start_angle) {",
            "    difference() {",
            f"        ring_segment(start_angle, {seg_sweep:.5f}, 0, ring_thickness, ring_inner_radius, ring_outer_radius);",
            "        translate([0, 0, ring_thickness - 2.0])",
            "            ring_segment(start_angle + 6, 168, 0, 3, ring_inner_radius + 2.5, ring_outer_radius - 2.5);",
            "    }",
            "}",
            "",
            "module gap_bridge_plate(center_angle) {",
            "    difference() {",
            "        ring_segment(center_angle - 6, 12, -2.0, 1.6, ring_inner_radius, ring_outer_radius);",
            "        rotate([0, 0, center_angle])",
            "            translate([ring_outer_radius - 4.0, 0, -2.2]) cylinder(h = 2.2, r = 1.2, $fn = 48);",
            "    }",
            "}",
            "",
            "module set_screw_hole(angle_deg) {",
            "    rotate([0, 0, angle_deg])",
            "        translate([ring_outer_radius - 3.5, 0, mount_plate_thick / 2])",
            "            rotate([90, 0, 0]) cylinder(h = 14, r = 1.6, center = true, $fn = 32);",
            "}",
            "",
            "module lock_screw_hole(angle_deg) {",
            "    rotate([0, 0, angle_deg])",
            "        translate([ring_outer_radius - 9.0, 0, mount_plate_thick / 2])",
            "            rotate([90, 0, 0]) cylinder(h = 14, r = 1.2, center = true, $fn = 32);",
            "}",
            "",
            "module u_mount_plate() {",
            "    difference() {",
            f"        ring_segment({mount_start:.5f}, {s.mount_plate_arc_deg:.5f}, 0, mount_plate_thick, open_hole_radius + 4.0, ring_outer_radius + 8.0);",
            "        cylinder(h = mount_plate_thick + 2, r = open_hole_radius, center = false, $fn = 180);",
            "        for (k = [0 : 3]) {",
            "            set_screw_hole(-45 + k * 30);",
            "            lock_screw_hole(-33 + k * 30);",
            "        }",
            f"        for (j = [0 : {mount_plate_magnet_count - 1}]) {{",
            f"            rotate([0, 0, {mount_start:.5f} + j * {mount_step:.5f} + {mount_step / 2.0:.5f}])",
            "                magnet_pocket(open_hole_radius + 8.0, mount_plate_thick - magnet_thickness);",
            "        }",
            "    }",
            "}",
            "",
            "module assembly_layout() {",
            f"    // Primary seam magnets per half: {len(primary_indices)}",
            f"    // Secondary seam magnets per half: {len(secondary_indices)}",
            f"    primary_half_ring({primary_start:.5f});",
            f"    rotate([0, 0, 180]) primary_half_ring({primary_start:.5f});",
            f"    translate([0, 0, ring_thickness + 0.2]) secondary_half_ring({secondary_start:.5f});",
            f"    translate([0, 0, ring_thickness + 0.2]) rotate([0, 0, 180]) secondary_half_ring({secondary_start:.5f});",
            "    gap_bridge_plate(0);",
            "    gap_bridge_plate(180);",
            "    translate([0, 0, ring_thickness * 2 + 2.0]) u_mount_plate();",
            "}",
            "",
            "assembly_layout();",
            "",
        ]
        return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate multipart encoder-ring OpenSCAD for bell gudgeon installs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--n-magnets", type=int, default=90)
    parser.add_argument("--magnet-width", type=float, default=5.0)
    parser.add_argument("--magnet-length", type=float, default=20.0)
    parser.add_argument("--magnet-thickness", type=float, default=2.0)
    parser.add_argument("--steel-inner-diameter", type=float, default=6.0 * MM_PER_INCH)
    parser.add_argument("--steel-outer-diameter", type=float, default=8.0 * MM_PER_INCH)
    parser.add_argument("--open-hole-diameter", type=float, default=MIN_OPEN_HOLE_DIAMETER_MM)
    parser.add_argument("--ring-thickness", type=float, default=6.0)
    parser.add_argument("--assembly-gap", type=float, default=1.0)
    parser.add_argument("--mount-plate-thickness", type=float, default=6.0)
    parser.add_argument("--mount-plate-arc-deg", type=float, default=250.0)
    parser.add_argument("--output", default="multipart_encoder_ring.scad")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    spec = MultipartEncoderSpec(
        n_magnets=args.n_magnets,
        magnet_width_mm=args.magnet_width,
        magnet_length_mm=args.magnet_length,
        magnet_thickness_mm=args.magnet_thickness,
        steel_inner_diameter_mm=args.steel_inner_diameter,
        steel_outer_diameter_mm=args.steel_outer_diameter,
        open_hole_diameter_mm=args.open_hole_diameter,
        ring_thickness_mm=args.ring_thickness,
        assembly_gap_mm=args.assembly_gap,
        mount_plate_thickness_mm=args.mount_plate_thickness,
        mount_plate_arc_deg=args.mount_plate_arc_deg,
        output_file=args.output,
    )
    scad = MultipartEncoderScadGenerator(spec).generate()
    MultipartOutputValidator.validate_scad(scad, spec)
    with open(spec.output_file, "w", encoding="utf-8") as handle:
        handle.write(scad)
    print(f"Wrote {spec.output_file}")
    print(f"  Ring ID/OD: {spec.steel_inner_diameter_mm:.1f} / {spec.steel_outer_diameter_mm:.1f} mm")
    print(f"  Open hole : {spec.open_hole_diameter_mm:.1f} mm (>= {MIN_OPEN_HOLE_DIAMETER_MM:.1f} mm)")
    print(f"  Magnets   : {spec.n_magnets} @ {spec.magnet_width_mm:.1f} mm tangential width")


if __name__ == "__main__":
    main()
