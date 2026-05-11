#!/usr/bin/env python3
"""
Generate SVG documentation drawings for the 10 in half-ring magnet cover.

This is a documentation-only generator.  It captures the requested design
intent for the half ring that snaps over a 1/8 in steel backing half ring and
its 20×5×2 mm radial magnets.
"""

from __future__ import annotations

import math
from pathlib import Path

INCH = 25.4


def design_data() -> dict:
    """Return the fixed design inputs and all derived dimensions.

    Axial stack (Z=0 = print-bed / bottom face, Z increases upward):
      z0 = 0              bottom of base (print-bed face)
      z1 = base           top of base / start of capture cavity
      z2 = z1 + magnet_clearance   top of magnet zone
      z3 = z2 + steel_t   top of steel zone (steel ring sits here)
      z4 = z3 + chamfer   top of chamfer lead-in  (open entry of cavity)
      z5 = z4 + snap      snap tooth tip (outermost wall height)

    The chamfer makes assembly easy: walls taper over z3→z4 then the 0.2 mm
    snap tooth protrudes inward at z4→z5 to retain the steel ring.
    """
    steel_inner_radius = 6.0 * INCH / 2.0   # 76.20 mm
    steel_outer_radius = 8.0 * INCH / 2.0   # 101.60 mm

    magnet_length = 20.0
    magnet_width = 5.0
    magnet_thickness = 2.0
    magnets_per_half = 45

    # ── Axial (Z) layer thicknesses ──────────────────────────────────
    base_thickness    = 1.0          # flat skin, print-bed face
    magnet_clearance  = 2.1          # magnet 2 mm + 0.1 mm clearance
    steel_thickness   = INCH / 8.0   # 3.175 mm  (1/8 in steel ring)
    chamfer_height    = 2.0          # lead-in taper above steel seat
    snap_overhang     = 0.2          # inward tooth at the open end

    # ── Derived Z positions ──────────────────────────────────────────
    z1 = base_thickness
    z2 = z1 + magnet_clearance
    z3 = z2 + steel_thickness
    z4 = z3 + chamfer_height
    z5 = z4 + snap_overhang

    # ── Radial layout ────────────────────────────────────────────────
    # Cover walls are 1/8 in on each side → 5.75 in ID / 8.25 in OD
    # Total radial span = 1.5 in = 38.1 mm
    cover_wall          = INCH / 8.0   # 3.175 mm
    cover_inner_radius  = steel_inner_radius - cover_wall   # 73.025 mm
    cover_outer_radius  = steel_outer_radius + cover_wall   # 104.775 mm

    # Magnet band is centred on the steel ring
    steel_margin        = (steel_outer_radius - steel_inner_radius - magnet_length) / 2.0
    magnet_inner_radius = steel_inner_radius + steel_margin
    magnet_outer_radius = magnet_inner_radius + magnet_length

    # Magnet-end walls (radial stops at each end of the 20 mm magnet)
    magnet_wall         = 2.04

    # Chamfer taper: how far the cavity flares outward at z4 relative to z3.
    # At z5 the snap tooth is snap_overhang inside the steel ring face,
    # so chamfer_taper must be > snap_overhang for the ring to enter freely.
    # 1.2 mm gives a comfortable 31° entry angle (2 mm axial, 1.2 mm radial).
    chamfer_taper       = 1.2

    # Magnet pocket corner fillet in the cavity: must be larger than the magnet's
    # own corner radius so the magnet seats fully.  Conservative = 0.5 mm.
    magnet_pocket_fillet = 0.5

    # Outer retention tabs (per-magnet, spring out 1 mm to grip steel OD)
    outer_tab_width     = 2.0
    outer_tab_overhang  = 1.0
    # Tab flex pocket: slot cut in outer wall to let tab spring outward
    tab_pocket_depth    = chamfer_height + snap_overhang   # full extra-wall zone

    pitch_angle    = math.tau / 90.0
    wedge_outer    = steel_outer_radius * pitch_angle - magnet_width
    wedge_inner    = steel_inner_radius * pitch_angle - magnet_width
    half_arc_outer = math.pi * steel_outer_radius
    used_arc_outer = magnets_per_half * (magnet_width + wedge_outer)

    return {
        # Radii
        "cover_inner_radius":  cover_inner_radius,
        "cover_outer_radius":  cover_outer_radius,
        "cover_radial_span":   cover_outer_radius - cover_inner_radius,
        "steel_inner_radius":  steel_inner_radius,
        "steel_outer_radius":  steel_outer_radius,
        "magnet_inner_radius": magnet_inner_radius,
        "magnet_outer_radius": magnet_outer_radius,
        # Magnet
        "magnet_length":    magnet_length,
        "magnet_width":     magnet_width,
        "magnet_thickness": magnet_thickness,
        "magnets_per_half": magnets_per_half,
        # Axial thicknesses
        "base_thickness":   base_thickness,
        "magnet_clearance": magnet_clearance,
        "steel_thickness":  steel_thickness,
        "chamfer_height":   chamfer_height,
        "snap_overhang":    snap_overhang,
        # Derived Z positions
        "z1": z1,  "z2": z2,  "z3": z3,  "z4": z4,  "z5": z5,
        # Wall geometry
        "cover_wall":        cover_wall,
        "magnet_wall":       magnet_wall,
        "chamfer_taper":     chamfer_taper,
        "magnet_pocket_fillet": magnet_pocket_fillet,
        "outer_tab_width":   outer_tab_width,
        "outer_tab_overhang": outer_tab_overhang,
        "tab_pocket_depth":  tab_pocket_depth,
        # Angular / arc maths
        "pitch_angle":     pitch_angle,
        "pitch_angle_deg": math.degrees(pitch_angle),
        "wedge_outer":     wedge_outer,
        "wedge_inner":     wedge_inner,
        "half_arc_outer":  half_arc_outer,
        "used_arc_outer":  used_arc_outer,
        "magnet_radial_spare": steel_outer_radius - magnet_outer_radius,
    }


def fmt_mm(value: float) -> str:
    return f"{value:.2f} mm"


def svg_header(width: float, height: float, title: str) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width:.1f}mm" height="{height:.1f}mm" '
            f'viewBox="0 0 {width:.1f} {height:.1f}">'
        ),
        f"  <title>{title}</title>",
        "  <defs>",
        '    <marker id="arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">',
        '      <path d="M0,0 L6,3 L0,6 Z" fill="#555"/>',
        "    </marker>",
        '    <marker id="arr2" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto">',
        '      <path d="M6,0 L0,3 L6,6 Z" fill="#555"/>',
        "    </marker>",
        "    <style>",
        "      .dim { stroke: #555; stroke-width: 0.5; marker-start: url(#arr2); marker-end: url(#arr); }",
        "      .callout { stroke: #555; stroke-width: 0.4; fill: none; marker-end: url(#arr); }",
        "      .text { font-family: sans-serif; fill: #333; }",
        "      .label { font-family: sans-serif; fill: #222; font-size: 4px; font-weight: bold; }",
        "      .note { font-family: sans-serif; fill: #555; font-size: 2.8px; }",
        "    </style>",
        "  </defs>",
        f'  <rect width="{width:.1f}" height="{height:.1f}" fill="white"/>',
    ]


def svg_footer(lines: list[str]) -> str:
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def ring_path(cx: float, cy: float, inner_r: float, outer_r: float, steps: int = 64) -> str:
    outer = []
    inner = []
    for i in range(steps + 1):
        angle = math.pi - (math.pi * i / steps)
        outer.append((cx + outer_r * math.cos(angle), cy - outer_r * math.sin(angle)))
        inner.append((cx + inner_r * math.cos(angle), cy - inner_r * math.sin(angle)))
    parts = [f"M {outer[0][0]:.3f},{outer[0][1]:.3f}"]
    parts.extend(f"L {x:.3f},{y:.3f}" for x, y in outer[1:])
    parts.append(f"L {inner[-1][0]:.3f},{inner[-1][1]:.3f}")
    parts.extend(f"L {x:.3f},{y:.3f}" for x, y in reversed(inner[:-1]))
    parts.append("Z")
    return " ".join(parts)


def magnet_polygon(cx: float, cy: float, angle: float, inner_r: float, outer_r: float, width: float) -> list[tuple[float, float]]:
    half_w = width / 2.0

    def to_xy(radius: float, tangential: float) -> tuple[float, float]:
        return (
            cx + radius * math.cos(angle) - tangential * math.sin(angle),
            cy - (radius * math.sin(angle) + tangential * math.cos(angle)),
        )

    return [
        to_xy(inner_r, -half_w),
        to_xy(inner_r, half_w),
        to_xy(outer_r, half_w),
        to_xy(outer_r, -half_w),
    ]


def points_attr(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.3f},{y:.3f}" for x, y in points)


def generate_cross_section_svg(data: dict) -> str:
    """Radial cross-section: base at BOTTOM (Z=0), walls extend upward.

    Axial layout (bottom to top):
      Z0=0       print-bed face (bottom of base)
      Z1         top of base / cavity floor
      Z2         magnet zone ceiling
      Z3         steel seat (ring rests here)
      Z4         top of chamfer lead-in (open mouth of cavity)
      Z5         snap tooth tip

    Radial layout (left to right):
      x=0        cover inner edge (5.75 in ID)
      x=cw       steel inner edge (6 in ID)
      x=cw+sw    steel outer edge (8 in OD)
      x=span     cover outer edge (8.25 in OD)
    """
    width = 300.0
    height = 170.0
    lines = svg_header(width, height, "10 in half-ring cover \u2014 radial cross section")

    # True-scale coordinate system
    # x-axis: radial position measured from the cover inner edge (left = cover ID)
    # y-axis: axial depth below the base bottom face (top of drawing = base outer face)
    x0 = 36.0          # SVG x of cover inner edge
    y_base_top = 38.0  # SVG y of base top face (outer/print-bed face)
    sx = 7.0            # mm → SVG units (radial)
    sy = 7.0            # mm → SVG units (axial, downward)

    def xp(mm: float) -> float:
        return x0 + mm * sx

    def yp_below(mm: float) -> float:
        """mm below base bottom face → SVG y (downward)."""
        return y_base_top + data["base_thickness"] * sy + mm * sy

    def yp_base(mm: float) -> float:
        """mm above base bottom face (into base) → SVG y (upward from base bottom)."""
        return y_base_top + data["base_thickness"] * sy - mm * sy

    # Radial offsets from cover inner edge
    cover_span  = data["cover_radial_span"]          # 31.75 mm
    steel_start = data["steel_inner_radius"] - data["cover_inner_radius"]  # 3.175 mm
    steel_end   = data["steel_outer_radius"]  - data["cover_inner_radius"]  # 28.575 mm
    mag_start   = data["magnet_inner_radius"] - data["cover_inner_radius"]  # 5.875 mm
    mag_end     = data["magnet_outer_radius"]  - data["cover_inner_radius"]  # 25.875 mm

    bt     = data["base_thickness"]      # 1.0 mm
    mt     = data["magnet_thickness"]    # 2.0 mm
    st     = data["steel_thickness"]     # 3.175 mm
    swe    = data["steel_wall_extra"]    # 1.0 mm
    wall_h = st + swe                    # 4.175 mm total wall depth below base
    snap   = data["snap_overhang"]       # 0.2 mm
    cw     = data["cover_wall"]          # 3.175 mm (1/8 in)

    cid = 2.0 * data["cover_inner_radius"] / INCH
    cod = 2.0 * data["cover_outer_radius"] / INCH

    # ── Title / legend ────────────────────────────────────────────────
    lines.append(
        f'  <text x="8" y="9" class="label">Half-ring cover \u2014 radial cross section (base at top, walls hang down)</text>'
    )
    lines.append(
        f'  <text x="8" y="14.5" class="note">True scale \u2014 gray: printed cover; dark gray: 1/8 in steel ring (reference); blue: 20\xd72 mm magnets. ID {cid:.3f} in / OD {cod:.3f} in.</text>'
    )

    # ── Radial span dimension above the base ─────────────────────────
    dim_y = y_base_top - 7.0
    lines.append(
        f'  <line x1="{xp(0):.2f}" y1="{dim_y:.2f}" x2="{xp(cover_span):.2f}" y2="{dim_y:.2f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{xp(cover_span / 2):.2f}" y="{dim_y - 2:.2f}" text-anchor="middle" class="text" font-size="3.1">'
        f'{cover_span / INCH:.3f} in = {cover_span:.2f} mm radial span</text>'
    )

    # ── Base plate (full span, 1 mm thick) ───────────────────────────
    lines.append(
        f'  <rect x="{xp(0):.2f}" y="{y_base_top:.2f}"'
        f' width="{cover_span * sx:.2f}" height="{bt * sy:.2f}"'
        f' fill="#d9d9d9" stroke="#666" stroke-width="0.5"/>'
    )

    # ── Inner capture wall (x=0 → x=steel_start, full wall_h deep) ───
    lines.append(
        f'  <rect x="{xp(0):.2f}" y="{yp_below(0):.2f}"'
        f' width="{steel_start * sx:.2f}" height="{wall_h * sy:.2f}"'
        f' fill="#c0c0c0" stroke="#666" stroke-width="0.5"/>'
    )

    # ── Outer capture wall (x=steel_end → x=cover_span, full wall_h deep) ──
    lines.append(
        f'  <rect x="{xp(steel_end):.2f}" y="{yp_below(0):.2f}"'
        f' width="{(cover_span - steel_end) * sx:.2f}" height="{wall_h * sy:.2f}"'
        f' fill="#c0c0c0" stroke="#666" stroke-width="0.5"/>'
    )

    # ── Magnet reference (blue, inside cavity against base bottom) ────
    lines.append(
        f'  <rect x="{xp(mag_start):.2f}" y="{yp_below(0):.2f}"'
        f' width="{(mag_end - mag_start) * sx:.2f}" height="{mt * sy:.2f}"'
        f' fill="#4a90d9" stroke="#2e6bb0" stroke-width="0.5"/>'
    )
    lines.append(
        f'  <text x="{xp((mag_start + mag_end) / 2):.2f}" y="{yp_below(mt / 2) + 1.2:.2f}"'
        f' text-anchor="middle" font-size="3.0" fill="white" font-family="sans-serif">20\xd72 mm magnet</text>'
    )

    # ── Steel ring reference (dark gray, below magnets) ───────────────
    lines.append(
        f'  <rect x="{xp(steel_start):.2f}" y="{yp_below(mt):.2f}"'
        f' width="{(steel_end - steel_start) * sx:.2f}" height="{st * sy:.2f}"'
        f' fill="#888" stroke="#555" stroke-width="0.5"/>'
    )
    lines.append(
        f'  <text x="{xp((steel_start + steel_end) / 2):.2f}" y="{yp_below(mt + st / 2) + 1.2:.2f}"'
        f' text-anchor="middle" font-size="3.0" fill="white" font-family="sans-serif">1/8 in steel ring</text>'
    )

    # ── Snap overhangs at the free (open) end of each capture wall ───
    # Inner snap: protrudes inward from inner wall's cavity-facing edge
    lines.append(
        f'  <rect x="{xp(steel_start):.2f}" y="{yp_below(wall_h):.2f}"'
        f' width="{snap * sx:.2f}" height="{snap * sy:.2f}"'
        f' fill="#777" stroke="#555" stroke-width="0.3"/>'
    )
    # Outer snap: protrudes inward from outer wall's cavity-facing edge
    lines.append(
        f'  <rect x="{xp(steel_end - snap):.2f}" y="{yp_below(wall_h):.2f}"'
        f' width="{snap * sx:.2f}" height="{snap * sy:.2f}"'
        f' fill="#777" stroke="#555" stroke-width="0.3"/>'
    )

    # ── Axial dimension lines (left side) ────────────────────────────
    left_dim_x = xp(-2.5)
    # Base thickness
    lines.append(
        f'  <line x1="{left_dim_x:.2f}" y1="{y_base_top:.2f}" x2="{left_dim_x:.2f}" y2="{yp_below(0):.2f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{left_dim_x - 1:.2f}" y="{(y_base_top + yp_below(0)) / 2 + 1:.2f}"'
        f' text-anchor="end" class="text" font-size="2.8">{bt:.1f}</text>'
    )
    # Wall depth
    lines.append(
        f'  <line x1="{left_dim_x - 3:.2f}" y1="{yp_below(0):.2f}" x2="{left_dim_x - 3:.2f}" y2="{yp_below(wall_h):.2f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{left_dim_x - 4:.2f}" y="{(yp_below(0) + yp_below(wall_h)) / 2 + 1:.2f}"'
        f' text-anchor="end" class="text" font-size="2.8">{wall_h:.3f}</text>'
    )

    # ── Radial dimension lines (bottom area) ─────────────────────────
    bot_y1 = yp_below(wall_h) + 9.0
    bot_y2 = bot_y1 + 8.0
    bot_y3 = bot_y2 + 8.0

    # Cover wall width (inner side)
    lines.append(
        f'  <line x1="{xp(0):.2f}" y1="{bot_y1:.2f}" x2="{xp(steel_start):.2f}" y2="{bot_y1:.2f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{xp(steel_start / 2):.2f}" y="{bot_y1 - 1.5:.2f}"'
        f' text-anchor="middle" class="text" font-size="2.8">{cw:.3f} (1/8 in)</text>'
    )

    # Steel ring width
    lines.append(
        f'  <line x1="{xp(steel_start):.2f}" y1="{bot_y2:.2f}" x2="{xp(steel_end):.2f}" y2="{bot_y2:.2f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{xp((steel_start + steel_end) / 2):.2f}" y="{bot_y2 - 1.5:.2f}"'
        f' text-anchor="middle" class="text" font-size="2.8">{steel_end - steel_start:.2f} mm (1 in) steel ring</text>'
    )

    # Total cover span (repeated at bottom for clarity)
    lines.append(
        f'  <line x1="{xp(0):.2f}" y1="{bot_y3:.2f}" x2="{xp(cover_span):.2f}" y2="{bot_y3:.2f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{xp(cover_span / 2):.2f}" y="{bot_y3 - 1.5:.2f}"'
        f' text-anchor="middle" class="text" font-size="2.8">cover: {cid:.3f} in ID to {cod:.3f} in OD</text>'
    )

    # ── Callout: snap detail ──────────────────────────────────────────
    snap_callout_x = xp(steel_start + snap / 2)
    snap_callout_y = yp_below(wall_h + snap)
    lines.append(
        f'  <path d="M {snap_callout_x:.2f},{snap_callout_y:.2f} L {xp(-1):.2f},{snap_callout_y + 8:.2f}" class="callout"/>'
    )
    lines.append(
        f'  <text x="{xp(-1.5):.2f}" y="{snap_callout_y + 10:.2f}" text-anchor="end" class="note">'
        f'0.2 mm snap on both inner and outer walls</text>'
    )

    return svg_footer(lines)


def generate_top_view_svg(data: dict) -> str:
    width = 265.0
    height = 180.0
    lines = svg_header(width, height, '10 in half-ring cover — top view')

    scale = 1.05
    cx = width / 2.0
    cy = 144.0

    def px(value: float) -> float:
        return value * scale

    cover_inner = px(data["cover_inner_radius"])
    cover_outer = px(data["cover_outer_radius"])
    steel_inner = px(data["steel_inner_radius"])
    steel_outer = px(data["steel_outer_radius"])
    mag_inner = px(data["magnet_inner_radius"])
    mag_outer = px(data["magnet_outer_radius"])
    tab_outer = px(data["steel_outer_radius"] + data["outer_tab_overhang"])

    lines.append(f'  <text x="8" y="9" class="label">10 in Half Ring Over Magnets — top view of one 180° printed half</text>')
    lines.append(
        f'  <text x="8" y="14.5" class="note">Light gray = printed half ring, dark gray = steel half ring reference, blue = magnets, pale gray = alignment wedges, red = 2 mm tabs extending 1 mm beyond the 8 in steel OD.</text>'
    )

    lines.append(
        f'  <path d="{ring_path(cx, cy, cover_inner, cover_outer)}" fill="#ececec" stroke="#666" stroke-width="0.8"/>'
    )
    lines.append(
        f'  <path d="{ring_path(cx, cy, steel_inner, steel_outer)}" fill="none" stroke="#888" stroke-width="0.7" stroke-dasharray="2 1"/>'
    )

    theta = data["pitch_angle"]
    start_angle = math.pi - theta / 2.0

    magnets = []
    for i in range(data["magnets_per_half"]):
        angle = start_angle - i * theta
        magnets.append((i, angle))

    # Wedges first so they sit behind magnets.
    half_w = data["magnet_width"] / 2.0
    wedge_inner_half = (data["magnet_width"] + data["wedge_inner"]) / 2.0
    wedge_outer_half = (data["magnet_width"] + data["wedge_outer"]) / 2.0
    for index, angle in magnets[:-1]:
        mid = angle - theta / 2.0

        def to_xy(radius: float, tangential: float) -> tuple[float, float]:
            return (
                cx + px(radius * math.cos(mid) - tangential * math.sin(mid)),
                cy - px(radius * math.sin(mid) + tangential * math.cos(mid)),
            )

        wedge = [
            to_xy(data["steel_inner_radius"], half_w),
            to_xy(data["steel_inner_radius"], wedge_inner_half),
            to_xy(data["steel_outer_radius"], wedge_outer_half),
            to_xy(data["steel_outer_radius"], half_w),
        ]
        lines.append(
            f'  <polygon points="{points_attr(wedge)}" fill="#d8d8d8" stroke="#c0c0c0" stroke-width="0.2"/>'
        )

    for index, angle in magnets:
        magnet = magnet_polygon(cx, cy, angle, mag_inner, mag_outer, px(data["magnet_width"]))
        lines.append(
            f'  <polygon points="{points_attr(magnet)}" fill="{"#4a90d9" if index % 2 == 0 else "#2e6bb0"}" stroke="white" stroke-width="0.35" opacity="0.97"/>'
        )

        tab = magnet_polygon(cx, cy, angle, px(data["steel_outer_radius"]), tab_outer, px(data["outer_tab_width"]))
        lines.append(
            f'  <polygon points="{points_attr(tab)}" fill="#d9534f" stroke="#b13d3a" stroke-width="0.2"/>'
        )

    # Main notes and dimensions.
    lines.append(
        f'  <line x1="{cx - cover_inner:.3f}" y1="{cy + 21:.3f}" x2="{cx + cover_inner:.3f}" y2="{cy + 21:.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{cx:.3f}" y="{cy + 17:.3f}" text-anchor="middle" class="text" font-size="3.1">{(2.0 * data["cover_inner_radius"] / INCH):.3f} in ID = {(2.0 * data["cover_inner_radius"]):.2f} mm</text>'
    )
    lines.append(
        f'  <line x1="{cx - cover_outer:.3f}" y1="{cy + 33:.3f}" x2="{cx + cover_outer:.3f}" y2="{cy + 33:.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{cx:.3f}" y="{cy + 29:.3f}" text-anchor="middle" class="text" font-size="3.1">{(2.0 * data["cover_outer_radius"] / INCH):.3f} in OD = {(2.0 * data["cover_outer_radius"]):.2f} mm</text>'
    )
    lines.append(
        f'  <path d="M {cx + steel_outer:.3f},{cy:.3f} L {width - 22:.3f},{45:.3f}" class="callout"/>'
    )
    lines.append(
        f'  <text x="{width - 20:.3f}" y="42" class="text" font-size="3.1">45 magnets / half ring</text>'
    )
    lines.append(
        f'  <text x="{width - 20:.3f}" y="47" class="note">20×5×2 mm each on the 6 in / 8 in steel half ring</text>'
    )
    lines.append(
        f'  <path d="M {cx + steel_outer * 0.35:.3f},{cy - steel_outer * 0.94:.3f} L {width - 28:.3f},{66:.3f}" class="callout"/>'
    )
    lines.append(
        f'  <text x="{width - 26:.3f}" y="63" class="text" font-size="3.1">derived wedge ≈ {data["wedge_outer"]:.2f} mm at 8 in steel OD</text>'
    )
    lines.append(
        f'  <text x="{width - 26:.3f}" y="68" class="note">90 magnets around the full ring = {data["pitch_angle_deg"]:.2f}° per magnet</text>'
    )
    lines.append(
        f'  <text x="{width - 26:.3f}" y="73" class="note">Same pitch narrows to {data["wedge_inner"]:.2f} mm at the 6 in steel ID</text>'
    )
    lines.append(
        f'  <path d="M {cx + tab_outer * 0.52:.3f},{cy - tab_outer * 0.62:.3f} L {width - 34:.3f},{91:.3f}" class="callout"/>'
    )
    lines.append(
        f'  <text x="{width - 32:.3f}" y="88" class="text" font-size="3.1">outer retention tabs</text>'
    )
    lines.append(
        f'  <text x="{width - 32:.3f}" y="93" class="note">2.0 mm tangential width, 1.0 mm radial overhang</text>'
    )
    lines.append(
        f'  <text x="8" y="{height - 11:.3f}" class="note">Math check: outer pitch = 2π × 101.6 / 90 = {(2.0 * data["half_arc_outer"] / 90.0):.2f} mm, so each 5.00 mm magnet leaves a wedge of {data["wedge_outer"]:.2f} mm at the 8 in steel OD.</text>'
    )
    lines.append(
        f'  <text x="8" y="{height - 6:.3f}" class="note">Magnets centered on the 6 in / 8 in steel ring leave {data["magnet_radial_spare"]:.2f} mm of radial margin to the 8 in OD, and the same angular pitch gives an inner wedge throat of {data["wedge_inner"]:.2f} mm.</text>'
    )

    return svg_footer(lines)


def project_point(x: float, y: float, z: float, sx: float, sy: float, ox: float, oy: float) -> tuple[float, float]:
    return (ox + x * sx + y * sx * 0.33, oy - z * sy - y * sy * 0.28)


def semi_ring_surface(inner_r: float, outer_r: float, z: float, steps: int = 48) -> list[tuple[float, float, float]]:
    outer = []
    inner = []
    for i in range(steps + 1):
        angle = math.pi - math.pi * i / steps
        outer.append((outer_r * math.cos(angle), outer_r * math.sin(angle), z))
        inner.append((inner_r * math.cos(angle), inner_r * math.sin(angle), z))
    return outer + list(reversed(inner))


def polygon_2d(points3d: list[tuple[float, float, float]], sx: float, sy: float, ox: float, oy: float) -> str:
    return " ".join(
        f"{px:.3f},{py:.3f}" for px, py in (project_point(x, y, z, sx, sy, ox, oy) for x, y, z in points3d)
    )


def generate_perspective_svg(data: dict) -> str:
    width = 265.0
    height = 170.0
    lines = svg_header(width, height, '10 in half-ring cover — top-side perspective')

    sx = 0.95
    sy = 0.95
    ox = 132.5
    oy = 124.0
    thickness = data["base_thickness"] + data["magnet_thickness"] + data["steel_thickness"] + data["steel_wall_extra"]

    lines.append(f'  <text x="8" y="9" class="label">10 in Half Ring Over Magnets — top-side perspective</text>')
    lines.append(
        f'  <text x="8" y="14.5" class="note">Oblique documentation view of the printed half ring with the top skin, underside capture volume, alignment wedges, and red outer tabs.</text>'
    )

    top = semi_ring_surface(data["cover_inner_radius"], data["cover_outer_radius"], 0.0)
    bottom = semi_ring_surface(data["cover_inner_radius"], data["cover_outer_radius"], thickness)
    lines.append(
        f'  <polygon points="{polygon_2d(bottom, sx, sy, ox + 8, oy + 8)}" fill="#cdcdcd" stroke="#888" stroke-width="0.6"/>'
    )
    lines.append(
        f'  <polygon points="{polygon_2d(top, sx, sy, ox, oy)}" fill="#e7e7e7" stroke="#666" stroke-width="0.8"/>'
    )

    # Split faces at each end.
    end_faces = [
        [
            (-data["cover_outer_radius"], 0.0, 0.0),
            (-data["cover_inner_radius"], 0.0, 0.0),
            (-data["cover_inner_radius"], 0.0, thickness),
            (-data["cover_outer_radius"], 0.0, thickness),
        ],
        [
            (data["cover_inner_radius"], 0.0, 0.0),
            (data["cover_outer_radius"], 0.0, 0.0),
            (data["cover_outer_radius"], 0.0, thickness),
            (data["cover_inner_radius"], 0.0, thickness),
        ],
    ]
    for face in end_faces:
        lines.append(
            f'  <polygon points="{polygon_2d(face, sx, sy, ox, oy)}" fill="#d8d8d8" stroke="#777" stroke-width="0.5"/>'
        )

    theta = data["pitch_angle"]
    start_angle = math.pi - theta / 2.0

    for i in range(data["magnets_per_half"]):
        angle = start_angle - i * theta
        magnet_top = []
        for radius, tangential in (
            (data["magnet_inner_radius"], -data["magnet_width"] / 2.0),
            (data["magnet_inner_radius"], data["magnet_width"] / 2.0),
            (data["magnet_outer_radius"], data["magnet_width"] / 2.0),
            (data["magnet_outer_radius"], -data["magnet_width"] / 2.0),
        ):
            x = radius * math.cos(angle) - tangential * math.sin(angle)
            y = radius * math.sin(angle) + tangential * math.cos(angle)
            magnet_top.append((x, y, -0.05))
        lines.append(
            f'  <polygon points="{polygon_2d(magnet_top, sx, sy, ox, oy)}" fill="{"#4a90d9" if i % 2 == 0 else "#2e6bb0"}" stroke="white" stroke-width="0.22" opacity="0.95"/>'
        )

        tab = []
        for radius, tangential in (
            (data["steel_outer_radius"], -data["outer_tab_width"] / 2.0),
            (data["steel_outer_radius"], data["outer_tab_width"] / 2.0),
            (data["steel_outer_radius"] + data["outer_tab_overhang"], data["outer_tab_width"] / 2.0),
            (data["steel_outer_radius"] + data["outer_tab_overhang"], -data["outer_tab_width"] / 2.0),
        ):
            x = radius * math.cos(angle) - tangential * math.sin(angle)
            y = radius * math.sin(angle) + tangential * math.cos(angle)
            tab.append((x, y, -0.1))
        lines.append(
            f'  <polygon points="{polygon_2d(tab, sx, sy, ox, oy)}" fill="#d9534f" stroke="#b13d3a" stroke-width="0.18"/>'
        )

    # Perspective notes.
    lines.append(
        f'  <path d="M 182,43 L 225,24" class="callout"/>'
    )
    lines.append(
        f'  <text x="227" y="22" class="text" font-size="3.1">1.0 mm top base</text>'
    )
    lines.append(
        f'  <text x="227" y="27" class="note">underside ribs drop below this skin</text>'
    )
    lines.append(
        f'  <path d="M 140,67 L 224,54" class="callout"/>'
    )
    lines.append(
        f'  <text x="226" y="52" class="text" font-size="3.1">alignment wedges follow the 45-magnet pitch</text>'
    )
    lines.append(
        f'  <text x="226" y="57" class="note">~{data["wedge_outer"]:.2f} mm at the 8 in steel OD, ~{data["wedge_inner"]:.2f} mm at the 6 in steel ID</text>'
    )
    lines.append(
        f'  <path d="M 181,106 L 229,98" class="callout"/>'
    )
    lines.append(
        f'  <text x="231" y="96" class="text" font-size="3.1">red tabs tighten the outer capture</text>'
    )
    lines.append(
        f'  <text x="231" y="101" class="note">2.0 mm wide × 1.0 mm overhang</text>'
    )
    lines.append(
        f'  <text x="8" y="{height - 11:.3f}" class="note">This view is intentionally illustrative rather than a manufacturable solid model: it shows the semi-circular {(2.0 * data["cover_inner_radius"] / INCH):.3f} in ID / {(2.0 * data["cover_outer_radius"] / INCH):.3f} in OD cover, the magnet array, and the snap-on retention details requested for the documentation pass.</text>'
    )

    return svg_footer(lines)


def write_outputs(output_dir: Path) -> None:
    data = design_data()
    outputs = {
        "half_ring_over_magnets_cross_section.svg": generate_cross_section_svg(data),
        "half_ring_over_magnets_top_view.svg": generate_top_view_svg(data),
        "half_ring_over_magnets_perspective.svg": generate_perspective_svg(data),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (output_dir / name).write_text(content, encoding="utf-8")

    print("Generated half-ring documentation assets:")
    for name in outputs:
        print(f"  - {output_dir / name}")
    print(f"  - 45 magnets/half, pitch {data['pitch_angle_deg']:.2f}°")
    print(f"  - pocket wall thickness {data['magnet_wall']:.2f} mm")
    print(f"  - outer wedge {data['wedge_outer']:.2f} mm, inner wedge {data['wedge_inner']:.2f} mm")
    print(f"  - radial margin to 8 in OD {data['magnet_radial_spare']:.2f} mm")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    write_outputs(repo_root / "images")


if __name__ == "__main__":
    main()
