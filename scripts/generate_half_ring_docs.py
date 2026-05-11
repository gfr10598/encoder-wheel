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
    """Return the fixed design inputs and derived dimensions."""
    steel_inner_radius = 6.0 * INCH / 2.0
    steel_outer_radius = 8.0 * INCH / 2.0

    magnet_length = 20.0
    magnet_width = 5.0
    magnet_thickness = 2.0
    magnets_per_half = 45

    base_thickness = 1.0
    magnet_wall = 2.04
    steel_thickness = INCH / 8.0
    steel_wall = INCH / 4.0 - 0.1
    steel_wall_extra = 1.0
    snap_overhang = 0.2
    outer_tab_width = 2.0
    outer_tab_overhang = 1.0
    cover_inner_radius = steel_inner_radius - steel_wall
    cover_outer_radius = steel_outer_radius + steel_wall
    steel_margin = (steel_outer_radius - steel_inner_radius - magnet_length) / 2.0
    magnet_inner_radius = steel_inner_radius + steel_margin
    magnet_outer_radius = magnet_inner_radius + magnet_length

    pitch_angle = math.tau / 90.0
    wedge_outer = steel_outer_radius * pitch_angle - magnet_width
    wedge_inner = steel_inner_radius * pitch_angle - magnet_width
    half_arc_outer = math.pi * steel_outer_radius
    used_arc_outer = magnets_per_half * (magnet_width + wedge_outer)

    return {
        "cover_inner_radius": cover_inner_radius,
        "cover_outer_radius": cover_outer_radius,
        "cover_radial_span": cover_outer_radius - cover_inner_radius,
        "steel_inner_radius": steel_inner_radius,
        "steel_outer_radius": steel_outer_radius,
        "steel_thickness": steel_thickness,
        "magnet_inner_radius": magnet_inner_radius,
        "magnet_outer_radius": magnet_outer_radius,
        "magnet_length": magnet_length,
        "magnet_width": magnet_width,
        "magnet_thickness": magnet_thickness,
        "magnets_per_half": magnets_per_half,
        "base_thickness": base_thickness,
        "magnet_wall": magnet_wall,
        "steel_wall": steel_wall,
        "steel_wall_extra": steel_wall_extra,
        "snap_overhang": snap_overhang,
        "outer_tab_width": outer_tab_width,
        "outer_tab_overhang": outer_tab_overhang,
        "wedge_outer": wedge_outer,
        "wedge_inner": wedge_inner,
        "pitch_angle": pitch_angle,
        "pitch_angle_deg": math.degrees(pitch_angle),
        "half_arc_outer": half_arc_outer,
        "used_arc_outer": used_arc_outer,
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
    width = 300.0
    height = 170.0
    lines = svg_header(width, height, '10 in half-ring cover — radial cross section')

    x0 = 58.0
    y_base_bottom = 132.0
    sx = 5.8
    sy = 5.8

    def x(mm: float) -> float:
        return x0 + mm * sx

    def y(mm: float) -> float:
        return y_base_bottom - mm * sy

    cover_span = data["cover_radial_span"]
    steel_start = data["steel_inner_radius"] - data["cover_inner_radius"]
    steel_end = data["steel_outer_radius"] - data["cover_inner_radius"]
    magnet_start = data["magnet_inner_radius"] - data["cover_inner_radius"]
    magnet_end = data["magnet_outer_radius"] - data["cover_inner_radius"]

    base_top = data["base_thickness"]
    magnet_top = base_top + data["magnet_thickness"]
    steel_top = magnet_top + data["steel_thickness"]
    clip_wall_depth = data["steel_thickness"] + data["steel_wall_extra"]
    wall_top = base_top + clip_wall_depth
    cover_id = 2.0 * data["cover_inner_radius"] / INCH
    cover_od = 2.0 * data["cover_outer_radius"] / INCH

    lines.append(f'  <text x="8" y="9" class="label">Half Ring Over Magnets — radial cross section through one magnet</text>')
    lines.append(
        f'  <text x="8" y="14.5" class="note">To-scale section (same X/Y scale): printed cover in gray, magnet in blue, steel backing ring in dark gray.</text>'
    )

    # Base plate.
    lines.append(
        f'  <rect x="{x(0):.3f}" y="{y(base_top):.3f}" width="{cover_span * sx:.3f}" height="{data["base_thickness"] * sy:.3f}" fill="#d9d9d9" stroke="#666" stroke-width="0.5"/>'
    )

    # Magnet stop walls.
    for wall_x in (magnet_start - data["magnet_wall"], magnet_end):
        lines.append(
            f'  <rect x="{x(wall_x):.3f}" y="{y(magnet_top):.3f}" width="{data["magnet_wall"] * sx:.3f}" height="{data["magnet_thickness"] * sy:.3f}" fill="#c7c7c7" stroke="#666" stroke-width="0.4"/>'
        )

    # Steel capture walls.
    for wall_x in (steel_start, steel_end - data["steel_wall"]):
        lines.append(
            f'  <rect x="{x(wall_x):.3f}" y="{y(wall_top):.3f}" width="{data["steel_wall"] * sx:.3f}" height="{clip_wall_depth * sy:.3f}" fill="#a8a8a8" stroke="#666" stroke-width="0.45"/>'
        )

    # Snap lips at steel-cavity top edge.
    left_lip_x = x(steel_start + data["steel_wall"] - data["snap_overhang"])
    right_lip_x = x(steel_end - data["steel_wall"])
    lip_y = y(wall_top + 0.12)
    lip_w = data["snap_overhang"] * sx
    lip_h = 0.55 * sy
    lines.append(
        f'  <rect x="{left_lip_x:.3f}" y="{lip_y:.3f}" width="{lip_w:.3f}" height="{lip_h:.3f}" fill="#8f8f8f" stroke="#666" stroke-width="0.3"/>'
    )
    lines.append(
        f'  <rect x="{right_lip_x:.3f}" y="{lip_y:.3f}" width="{lip_w:.3f}" height="{lip_h:.3f}" fill="#8f8f8f" stroke="#666" stroke-width="0.3"/>'
    )

    # Assembly inserts for context.
    lines.append(
        f'  <rect x="{x(magnet_start):.3f}" y="{y(magnet_top):.3f}" width="{data["magnet_length"] * sx:.3f}" height="{data["magnet_thickness"] * sy:.3f}" fill="#4a90d9" stroke="#2e6bb0" stroke-width="0.5"/>'
    )
    lines.append(
        f'  <rect x="{x(steel_start):.3f}" y="{y(steel_top):.3f}" width="{(steel_end - steel_start) * sx:.3f}" height="{data["steel_thickness"] * sy:.3f}" fill="#8a8a8a" stroke="#555" stroke-width="0.5"/>'
    )

    # Labels inside solids.
    lines.append(
        f'  <text x="{x(cover_span / 2):.3f}" y="{y(0.60):.3f}" text-anchor="middle" class="text" font-size="3.1">1.0 mm base, {cover_span:.2f} mm radial span ({cover_id:.2f} in ID to {cover_od:.2f} in OD)</text>'
    )
    lines.append(
        f'  <text x="{x((magnet_start + magnet_end) / 2):.3f}" y="{y(base_top + 1.2):.3f}" text-anchor="middle" font-size="3.2" fill="white" font-family="sans-serif">20×2 mm magnet section</text>'
    )
    lines.append(
        f'  <text x="{x((steel_start + steel_end) / 2):.3f}" y="{y(magnet_top + 1.55):.3f}" text-anchor="middle" font-size="3.2" fill="white" font-family="sans-serif">1/8 in steel ring</text>'
    )

    # Main dimensions.
    lines.append(
        f'  <line x1="{x(0):.3f}" y1="{y(9.0):.3f}" x2="{x(cover_span):.3f}" y2="{y(9.0):.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{x(cover_span / 2):.3f}" y="{y(9.45):.3f}" text-anchor="middle" class="text" font-size="3.1">{(cover_span / INCH):.3f} in radial base span = {cover_span:.2f} mm</text>'
    )
    lines.append(
        f'  <line x1="{x(-2.0):.3f}" y1="{y(0):.3f}" x2="{x(-2.0):.3f}" y2="{y(base_top):.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{x(-2.6):.3f}" y="{y(0.62):.3f}" text-anchor="end" class="text" font-size="3.0">1.0</text>'
    )
    lines.append(
        f'  <line x1="{x(-4.0):.3f}" y1="{y(base_top):.3f}" x2="{x(-4.0):.3f}" y2="{y(magnet_top):.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{x(-4.6):.3f}" y="{y(base_top + 1.1):.3f}" text-anchor="end" class="text" font-size="3.0">2.0</text>'
    )
    lines.append(
        f'  <line x1="{x(-6.0):.3f}" y1="{y(magnet_top):.3f}" x2="{x(-6.0):.3f}" y2="{y(steel_top):.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{x(-6.6):.3f}" y="{y(magnet_top + 1.8):.3f}" text-anchor="end" class="text" font-size="3.0">3.175</text>'
    )
    lines.append(
        f'  <line x1="{x(-8.1):.3f}" y1="{y(base_top):.3f}" x2="{x(-8.1):.3f}" y2="{y(wall_top):.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{x(-8.7):.3f}" y="{y(base_top + 2.2):.3f}" text-anchor="end" class="text" font-size="3.0">4.175 wall depth</text>'
    )
    lines.append(
        f'  <line x1="{x(magnet_start - data["magnet_wall"]):.3f}" y1="{y(7.1):.3f}" x2="{x(magnet_start):.3f}" y2="{y(7.1):.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{x(magnet_start - data["magnet_wall"] / 2):.3f}" y="{y(7.45):.3f}" text-anchor="middle" class="text" font-size="3.0">2.04 wall</text>'
    )
    lines.append(
        f'  <line x1="{x(steel_start):.3f}" y1="{y(10.3):.3f}" x2="{x(steel_start + data["steel_wall"]):.3f}" y2="{y(10.3):.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{x(steel_start + data["steel_wall"] / 2):.3f}" y="{y(10.65):.3f}" text-anchor="middle" class="text" font-size="3.0">{data["steel_wall"]:.2f} wall</text>'
    )
    lines.append(
        f'  <line x1="{left_lip_x:.3f}" y1="{y(wall_top + 1.3):.3f}" x2="{left_lip_x + lip_w:.3f}" y2="{y(wall_top + 1.3):.3f}" class="dim"/>'
    )
    lines.append(
        f'  <text x="{left_lip_x + lip_w / 2:.3f}" y="{y(wall_top + 1.65):.3f}" text-anchor="middle" class="text" font-size="3.0">0.2 snap lip</text>'
    )

    # Radius callouts.
    lines.append(
        f'  <path d="M {x(steel_start):.3f},{y(steel_top + 0.8):.3f} L {x(cover_span + 1.5):.3f},{y(steel_top + 1.8):.3f}" class="callout"/>'
    )
    lines.append(
        f'  <text x="{x(cover_span + 2.1):.3f}" y="{y(steel_top + 2.1):.3f}" class="note">6 in ID steel starts +{steel_start:.2f} mm from cover ID</text>'
    )
    lines.append(
        f'  <path d="M {x(magnet_start):.3f},{y(base_top + 0.4):.3f} L {x(2.2):.3f},{y(base_top - 2.1):.3f}" class="callout"/>'
    )
    lines.append(
        f'  <text x="{x(2.0):.3f}" y="{y(base_top - 2.3):.3f}" text-anchor="end" class="note">magnet band centered on steel ring</text>'
    )
    lines.append(
        f'  <text x="{x((steel_start + steel_end) / 2):.3f}" y="{y(-1.6):.3f}" text-anchor="middle" class="note">steel-capture walls shown on both sides of the 1/8 in steel ring</text>'
    )
    lines.append(
        f'  <text x="8" y="160" class="note">Stack shown to scale from base upward: 1.0 mm base, 2.0 mm magnet layer, 3.175 mm steel thickness, 1.0 mm extra wall extension, and 0.2 mm snap overhang.</text>'
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
