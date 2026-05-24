#!/usr/bin/env python3
"""
Validate internal consistency of magnet_pocket/config.yaml.

Each check is named (V1–V12) and corresponds to the rules in DESIGN.md.
Prints PASS/FAIL for each rule with the computed values, then exits
with code 0 if all pass or 1 if any fail.

Usage:
    python magnet_pocket/validate_config.py [config.yaml]
"""

import math
import sys
from pathlib import Path

import yaml


def load(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def check(label: str, name: str, condition: bool, detail: str, failures: list) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  {status}  {label:4s} {name:35s}  {detail}")
    if not condition:
        failures.append(label)


_REQUIRED_KEYS: dict[str, list[str]] = {
    "magnet": [
        "radial_mm",
        "tangential_mm",
        "axial_mm",
        "edge_radius_axial_mm",
        "edge_radius_other_mm",
    ],
    "holder": [
        "magnet_count",
        "ID_mm",
        "thickness_mm",
        "end_face_mm",
        "clearance_mm",
        "bore_snap_mm",
    ],
    "comb": [
        "count",
        "thickness_mm",
        "axial_gap",
        "clearance_mm",
        "snap_overhang_mm",
        "snap_type",
    ],
}

_MIN_PRINTABLE_WALL_MM = 0.8  # practical lower bound for FDM


def check_required_keys(cfg: dict) -> list[str]:
    """Return list of missing key paths; empty means all present."""
    missing = []
    for section, keys in _REQUIRED_KEYS.items():
        if section not in cfg:
            missing.append(section)
            continue
        for key in keys:
            if key not in cfg[section]:
                missing.append(f"{section}.{key}")
    return missing


def validate(cfg: dict) -> list[str]:
    """Run all validation checks; return list of failing rule IDs."""
    missing = check_required_keys(cfg)
    if missing:
        print(f"\nERROR: missing required config keys: {missing}")
        return ["KEYS"]

    m = cfg["magnet"]
    h = cfg["holder"]
    c = cfg["comb"]

    R_i = h["ID_mm"] / 2
    R_o = R_i + h["thickness_mm"]
    W_i = math.pi * h["ID_mm"] / h["magnet_count"]  # arc width at bore
    H = m["axial_mm"] + 2 * h["end_face_mm"]  # cell axial height
    tooth_pitch = H / (2 * c["count"])
    # axial_gap is the design gap between adjacent teeth (not fit clearance)
    tooth_width = tooth_pitch - c["axial_gap"]
    outer_wall = h["thickness_mm"] - m["radial_mm"] - h["clearance_mm"]
    tangential_needed = (
        m["tangential_mm"]
        + h["clearance_mm"]
        + c[
            "thickness_mm"
        ]  # one tooth (interleaved; only one tooth present at any cross-section)
        + c["clearance_mm"]
    )

    failures: list[str] = []

    print("\nDerived dimensions:")
    print(f"  R_i (bore radius)          = {R_i:.3f} mm")
    print(f"  R_o (outer radius)         = {R_o:.3f} mm")
    print(f"  W_i (arc width at bore)    = {W_i:.3f} mm")
    print(f"  H   (cell axial height)    = {H:.3f} mm")
    print(f"  tooth pitch                = {tooth_pitch:.3f} mm")
    print(f"  tooth width (after axial_gap) = {tooth_width:.3f} mm")
    print(f"  outer wall remaining       = {outer_wall:.3f} mm")
    print(
        f"  tangential space needed    = {tangential_needed:.3f} mm  (limit {W_i:.3f} mm)"
    )

    print("\nValidation checks:")
    check(
        "V1",
        "Even magnet count",
        h["magnet_count"] % 2 == 0,
        f"magnet_count = {h['magnet_count']}",
        failures,
    )

    check(
        "V2",
        "Radial fit (magnet < wall)",
        m["radial_mm"] + h["clearance_mm"] < h["thickness_mm"],
        f"{m['radial_mm']} + {h['clearance_mm']} = {m['radial_mm']+h['clearance_mm']:.3f}  <  {h['thickness_mm']}?",
        failures,
    )

    check(
        "V3",
        "Outer wall printable",
        outer_wall >= _MIN_PRINTABLE_WALL_MM,
        f"outer wall = {outer_wall:.3f} mm  (min {_MIN_PRINTABLE_WALL_MM} mm)",
        failures,
    )

    check(
        "V4",
        "Tangential fit at bore",
        tangential_needed <= W_i,
        f"need {tangential_needed:.3f} mm,  have {W_i:.3f} mm  (slack {W_i - tangential_needed:.3f} mm)",
        failures,
    )

    check(
        "V5",
        "Comb tooth width positive",
        tooth_width > 0,
        f"tooth width = pitch({tooth_pitch:.3f}) - axial_gap({c['axial_gap']}) = {tooth_width:.3f} mm",
        failures,
    )

    check(
        "V6",
        "Comb tooth depth > clearance",
        c["thickness_mm"] > c["clearance_mm"],
        f"{c['thickness_mm']} > {c['clearance_mm']}?",
        failures,
    )

    check(
        "V7",
        "Snap ≤ half tooth depth",
        c["snap_overhang_mm"] <= c["thickness_mm"] / 2,
        f"{c['snap_overhang_mm']} ≤ {c['thickness_mm']/2}?",
        failures,
    )

    check(
        "V8",
        "Bore snap ≤ edge radius",
        h["bore_snap_mm"] <= m["edge_radius_other_mm"],
        f"bore_snap {h['bore_snap_mm']} ≤ edge_radius_other {m['edge_radius_other_mm']}?",
        failures,
    )

    axial_fillet_limit = min(m["tangential_mm"], m["radial_mm"]) / 2
    check(
        "V9",
        "Axial fillet fits on edge",
        m["edge_radius_axial_mm"] <= axial_fillet_limit,
        f"{m['edge_radius_axial_mm']} ≤ {axial_fillet_limit:.3f}?",
        failures,
    )

    # bore-face edges span axial × tangential; radial_mm is not a limiting dimension here
    other_fillet_limit = min(m["axial_mm"], m["tangential_mm"]) / 2
    check(
        "V10",
        "Other fillet fits on edge",
        m["edge_radius_other_mm"] <= other_fillet_limit,
        f"{m['edge_radius_other_mm']} ≤ {other_fillet_limit:.3f}?",
        failures,
    )

    check(
        "V11",
        "End face positive",
        h["end_face_mm"] > 0,
        f"end_face_mm = {h['end_face_mm']}",
        failures,
    )

    valid_snap_types = ("full", "edges", "corners")
    snap_type = c.get("snap_type", "<missing>")
    check(
        "V13",
        "snap_type valid",
        snap_type in valid_snap_types,
        f"snap_type = '{snap_type}'  (allowed: {valid_snap_types})",
        failures,
    )

    snap_space_available = W_i - m["tangential_mm"]
    snap_space_needed = c["thickness_mm"] + c["snap_overhang_mm"] + c["clearance_mm"]
    check(
        "V14",
        "Snap deflection clears adjacent magnet",
        snap_space_available > snap_space_needed,
        f"(W_i - tangential) = {snap_space_available:.3f} mm  >  "
        f"tooth({c['thickness_mm']}) + overhang({c['snap_overhang_mm']}) + clearance({c['clearance_mm']}) = {snap_space_needed:.3f}?",
        failures,
    )

    return failures


def main() -> None:
    config_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).parent / "config.yaml"
    )
    print(f"Config: {config_path}")
    cfg = load(config_path)

    failures = validate(cfg)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s) did not pass: {', '.join(failures)}")
        sys.exit(1)
    else:
        print("All checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
