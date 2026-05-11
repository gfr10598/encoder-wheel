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
    """Radial cross-section sliced from the build123d cover solid at Y=0.

    The ExportSVG geometry group uses transform="scale(1,-1)", which means
    SVG root coordinates map directly to design coordinates:
        SVG x = radial position (mm),  left = cover ID, right = cover OD
        SVG y = axial position (mm),   top  = z=0 (base/bed), bottom = z=z5

    Deferred imports avoid the circular dependency:
        generate_half_ring_docs  ←  (design_data)  ←  generate_half_ring_3d
    """
    # Deferred imports — avoid circular dependency and make build123d optional
    # for scripts that only need design_data().
    import os
    import tempfile
    import xml.etree.ElementTree as ET
    from generate_half_ring_3d import make_cover
    from build123d import Axis, Box, Align, Color, ExportSVG

    # ── 1. Build cover and extract +Y face of Y=0 cross-section ──────
    cover = make_cover(data)
    slab = Box(300, 0.01, 30, align=(Align.CENTER, Align.CENTER, Align.MIN))
    section = cover.intersect(slab)
    xz_face = next(
        f for f in section.faces()
        if f.normal_at().Y > 0.9 and f.bounding_box().min.X > 0
    )

    # ── 2. Rotate +90° around X: (x,0,z)→(x,−z,0) → face in XY plane ─
    #    ExportSVG's "scale(1,−1)" group then renders at (x, z) on screen,
    #    so SVG root coords (x, y) = design (x_mm, z_mm) directly.
    rotated = xz_face.rotate(Axis.X, 90)

    # ── 3. Export geometry to temp SVG ────────────────────────────────
    fd, tmppath = tempfile.mkstemp(suffix=".svg")
    os.close(fd)
    exporter = ExportSVG(scale=1, margin=2)
    exporter.add_layer(
        "cover",
        fill_color=Color(0.84, 0.84, 0.84),
        line_color=Color(0.35, 0.35, 0.35),
        line_weight=0.4,
    )
    exporter.add_shape(rotated, layer="cover")
    exporter.write(tmppath)

    # ── 4. Parse temp SVG, extract geometry group ─────────────────────
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    tree = ET.parse(tmppath)
    os.unlink(tmppath)
    svg_root = tree.getroot()
    ns = "{http://www.w3.org/2000/svg}"
    vb_x, vb_y, vb_w, vb_h = (
        float(v) for v in svg_root.attrib["viewBox"].split()
    )
    geom_group = svg_root.find(f"{ns}g")
    geom_xml = ET.tostring(geom_group, encoding="unicode")

    # ── 5. Design values ──────────────────────────────────────────────
    cir = data["cover_inner_radius"]    # 73.025 mm
    cor = data["cover_outer_radius"]    # 104.775 mm
    sir = data["steel_inner_radius"]    # 76.200 mm
    sor = data["steel_outer_radius"]    # 101.600 mm
    mir = data["magnet_inner_radius"]
    mor = data["magnet_outer_radius"]
    z1, z2, z3, z4, z5 = data["z1"], data["z2"], data["z3"], data["z4"], data["z5"]
    mt   = data["magnet_thickness"]
    cw   = data["cover_wall"]
    cid  = 2 * cir / INCH
    cod  = 2 * cor / INCH

    # ── 6. Expand viewBox for annotation margins ──────────────────────
    left_margin  = 32   # space for Z bracket labels
    top_margin   = 10   # space for title + radial tick labels
    bot_margin   = 12   # space for bottom dimension arrows
    right_margin = 6

    nx  = vb_x - left_margin
    ny  = vb_y - top_margin
    nw  = vb_w + left_margin + right_margin
    nh  = vb_h + top_margin + bot_margin

    # Coordinate helper: convert (x_design, z_design) → SVG attribute strings
    def fx(v: float) -> str: return f"{v:.3f}"
    def fy(v: float) -> str: return f"{v:.3f}"

    def line(x1, y1, x2, y2, **attrs) -> str:
        a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        return (f'<line x1="{fx(x1)}" y1="{fy(y1)}" '
                f'x2="{fx(x2)}" y2="{fy(y2)}" {a}/>')

    def text(x, y, msg, anchor="middle", size=2.2, bold=False, color="#333") -> str:
        fw = "bold" if bold else "normal"
        return (f'<text x="{fx(x)}" y="{fy(y)}" text-anchor="{anchor}" '
                f'font-family="sans-serif" font-size="{size}" '
                f'font-weight="{fw}" fill="{color}">{msg}</text>')

    def rect(x, y, w, h, fill, opacity=0.65, stroke="none") -> str:
        return (f'<rect x="{fx(x)}" y="{fy(y)}" width="{w:.3f}" height="{h:.3f}" '
                f'fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}"/>')

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (f'<svg xmlns="http://www.w3.org/2000/svg" '
         f'width="{nw:.1f}mm" height="{nh:.1f}mm" '
         f'viewBox="{nx:.3f} {ny:.3f} {nw:.3f} {nh:.3f}">'),
        # Arrow marker defs
        '<defs>',
        '  <marker id="a1" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto">',
        '    <path d="M0,0 L5,2.5 L0,5 Z" fill="#555"/></marker>',
        '  <marker id="a2" markerWidth="5" markerHeight="5" refX="1" refY="2.5" orient="auto">',
        '    <path d="M5,0 L0,2.5 L5,5 Z" fill="#555"/></marker>',
        '</defs>',
    ]

    # ── Title ─────────────────────────────────────────────────────────
    parts.append(text((cir + cor) / 2, ny + 4,
                      "10 in half-ring cover \u2014 radial cross-section (1:1 scale)",
                      size=3.2, bold=True, color="#222"))
    parts.append(text((cir + cor) / 2, ny + 8,
                      f"ID {cid:.3f} in / OD {cod:.3f} in  \u2022  "
                      f"all dimensions in mm unless noted",
                      size=2.2, color="#666"))

    # ── Zone fill bands (inside the cavity) ───────────────────────────
    # Magnet clearance zone (z1→z2, full cavity width)
    parts.append(rect(sir, z1, sor - sir, z2 - z1, "#4a90e2", opacity=0.25))
    # Magnet reference body (z1→z1+mt, mir→mor)
    parts.append(rect(mir, z1, mor - mir, mt, "#2e6bb0", opacity=0.55))
    # Steel ring reference (z2→z3, sir→sor)
    parts.append(rect(sir, z2, sor - sir, z3 - z2, "#666", opacity=0.55))
    # Steel zone label
    parts.append(text((sir + sor) / 2, z2 + (z3 - z2) / 2 + 0.7,
                      "steel ring (ref)", size=1.8, color="white"))
    # Magnet label
    parts.append(text((mir + mor) / 2, z1 + mt / 2 + 0.6,
                      "magnet (ref)", size=1.8, color="white"))

    # ── Geometry (ExportSVG output) ────────────────────────────────────
    parts.append(geom_xml)

    # ── Horizontal zone boundary lines ────────────────────────────────
    for z_val, dash in [(z1, "1,1.5"), (z2, "1,1.5"), (z3, "1,1.5"),
                        (z4, "0.5,1"), (z5, "0.5,1")]:
        parts.append(
            f'<line x1="{fx(cir - 1)}" y1="{fy(z_val)}" '
            f'x2="{fx(cor + 1)}" y2="{fy(z_val)}" '
            f'stroke="#aaa" stroke-width="0.25" stroke-dasharray="{dash}"/>'
        )

    # ── Left-side Z zone brackets ──────────────────────────────────────
    bx  = cir - 3     # bracket x
    lx  = cir - 4     # label x
    zones = [
        (0,  z1, f"base  {z1:.1f}"),
        (z1, z2, f"magnet  {z2 - z1:.1f}"),
        (z2, z3, f"steel  {z3 - z2:.3f}"),
        (z3, z4, f"chamfer  {z4 - z3:.1f}"),
        (z4, z5, f"snap  {z5 - z4:.1f}"),
    ]
    for z_bot, z_top, label in zones:
        mid = (z_bot + z_top) / 2
        tick = 0.8
        parts.append(line(bx - tick, z_bot, bx, z_bot,
                          stroke="#555", **{"stroke-width": "0.35"}))
        parts.append(line(bx - tick, z_top, bx, z_top,
                          stroke="#555", **{"stroke-width": "0.35"}))
        parts.append(line(bx, z_bot, bx, z_top,
                          stroke="#555", **{"stroke-width": "0.35"}))
        parts.append(text(lx, mid + 0.7, label, anchor="end", size=2.0))

    # ── Top radial tick marks and labels ──────────────────────────────
    tick_top = vb_y - 0.5
    radials = [
        (cir, f"cover ID\n{cid:.3f} in"),
        (sir, f"steel ID\n6.000 in"),
        (sor, f"steel OD\n8.000 in"),
        (cor, f"cover OD\n{cod:.3f} in"),
    ]
    for rx, rlabel in radials:
        parts.append(line(rx, 0.0, rx, tick_top,
                          stroke="#555", **{"stroke-width": "0.3",
                                           "stroke-dasharray": "0.5,0.8"}))
        lines_list = rlabel.split("\n")
        for i, ln in enumerate(lines_list):
            ty = tick_top - 1.5 - (len(lines_list) - 1 - i) * 2.8
            parts.append(text(rx, ty, ln, size=2.0))

    # ── Bottom wall-width dimension arrows ─────────────────────────────
    arrow_y = vb_y + vb_h + 4
    for x1v, x2v, lbl in [
        (cir, sir, f"{cw:.3f} mm (⅛ in)"),
        (sor, cor, f"{cw:.3f} mm (⅛ in)"),
    ]:
        mx = (x1v + x2v) / 2
        parts.append(
            f'<line x1="{fx(x1v)}" y1="{fy(arrow_y)}" '
            f'x2="{fx(x2v)}" y2="{fy(arrow_y)}" '
            f'stroke="#555" stroke-width="0.4" '
            f'marker-start="url(#a2)" marker-end="url(#a1)"/>'
        )
        parts.append(text(mx, arrow_y + 3.5, lbl, size=2.0))

    parts.append("</svg>")
    return "\n".join(parts)





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
    thickness = data["z5"]   # total axial height = snap tip

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
