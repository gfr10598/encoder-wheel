#!/usr/bin/env python3
"""Generate a simple SVG + PNG diagram showing sensor vs magnet placement.

Produces a 2x2 panel: Top view, radial cross-section, tangential cross-section, perspective.
"""
import os, yaml, math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

def mm(x):
    return x

def draw(cfg, outdir):
    outer = cfg['outer_radius_mm']
    mag = cfg['magnet_dims_mm']
    mag_radial = mag[0]
    mag_thick = mag[2]
    sensor_offset = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset))
    # axial airgap above magnet face; default 5 mm
    airgap = float(cfg.get('airgap_plot_mm', 5.0))
    # approximate steel ring inner radius (default span 25.4 mm if not provided)
    steel_back_thickness = float(cfg.get('steel_backing_thickness_mm', 3.175))
    steel_inner = float(cfg.get('steel_inner_radius_mm', outer - 25.4))
    steel_outer = outer

    fig, axes = plt.subplots(2,2, figsize=(10,8))
    ax = axes[0,0]
    # Top view: disk and one magnet sector, sensor dot
    ax.set_title('Top view')
    # draw a short segment of inner/outer circumferences to indicate disk
    seg_ang = 30.0
    thetas = np.linspace(-math.radians(seg_ang)/2, math.radians(seg_ang)/2, 50)
    xs_outer = steel_outer * np.cos(thetas)
    ys_outer = steel_outer * np.sin(thetas)
    xs_inner = steel_inner * np.cos(thetas)
    ys_inner = steel_inner * np.sin(thetas)
    ax.plot(xs_outer, ys_outer, color='k', lw=1.2)
    ax.plot(xs_inner, ys_inner, color='k', lw=1.2)
    # magnet center radius
    r_center = outer - mag_radial/2.0
    mag_width = mag[1]
    # draw magnet so its outer radial face aligns with disk outer edge (x = steel_outer)
    mag_x0 = outer - mag_radial
    mag_y0 = -mag_width/2.0
    ax.add_patch(Rectangle((mag_x0, mag_y0), mag_radial, mag_width, color='C1', alpha=0.95))
    # top view: sensor projection on plane (show radial location)
    ax.plot([sensor_r], [0], 'o', color='C2', markersize=6)
    ax.text(sensor_r+2, 2, f'sensor r={sensor_r:.1f} mm, z={airgap:.1f} mm', color='C2')
    # zoom to a 3x3 inch patch (76.2 mm) centered on the magnet center
    size_mm = 76.2
    ax.set_xlim(r_center - size_mm/2.0, r_center + size_mm/2.0)
    ax.set_ylim(-size_mm/2.0, size_mm/2.0)
    ax.set_aspect('equal')

    # Radial cross-section (XZ)
    ax = axes[0,1]
    ax.set_title('Radial cross-section')
    # draw magnet block (radial orientation) and show inner/outer disk edges
    mag_x = outer - mag_radial
    ax.add_patch(Rectangle((mag_x, 0), mag_radial, mag_thick, color='C1'))
    # draw steel backing as a radial band between its upper and lower faces
    # place steel upper face at z = 0 (1/8" disk top at z=0)
    steel_top = 0.0
    steel_bottom = -steel_back_thickness
    # fill steel region between steel_inner and steel_outer
    ax.add_patch(Rectangle((steel_inner, steel_bottom), steel_outer - steel_inner, steel_top - steel_bottom, color='0.7', alpha=0.4))
    # sensor plotted at (radial, z = magnet top face + airgap)
    sensor_z = mag_thick + airgap
    sensor_x = sensor_r
    ax.plot([sensor_x], [sensor_z], 'o', color='C2', markersize=6)
    ax.annotate(f'z={sensor_z:.1f} mm', xy=(sensor_x, sensor_z), xytext=(sensor_x+5, sensor_z+5), arrowprops=dict(arrowstyle='->', color='C2'), color='C2')
    ax.axvline(steel_inner, color='0.2', linestyle='--', label='steel inner')
    ax.axvline(steel_outer, color='0.2', linestyle='-', label='steel outer')
    ax.set_xlim(steel_inner-10, steel_outer+10)
    # extend vertical limits to include steel thickness below face
    zmin = min(steel_bottom - 5, -5)
    zmax = max(mag_thick + airgap + 5, mag_thick + 5)
    ax.set_ylim(zmin, zmax)
    ax.set_xlabel('radial (mm)'); ax.set_ylabel('z (mm)')

    # Tangential cross-section (YZ)
    ax = axes[1,0]
    ax.set_title('Tangential cross-section')
    # tangential: show magnet width and sensor offset; show inner/outer circumferences as markers
    # tangential: use magnet tangential width and show sensor at centerline (tangential=0)
    mag_width = mag[1]
    ax.add_patch(Rectangle((-mag_width/2.0, 0), mag_width, mag_thick, color='C1', alpha=0.7))
    ax.plot([0], [sensor_z], 'o', color='C2', markersize=6)
    ax.annotate(f'z={sensor_z:.1f} mm', xy=(0, sensor_z), xytext=(mag_width*0.4, sensor_z+5), arrowprops=dict(arrowstyle='->', color='C2'), color='C2')
    ax.plot([steel_inner - r_center, steel_outer - r_center],[0,0], color='0.3', lw=1.0)
    ax.set_xlim(-mag_width, mag_width); ax.set_ylim(-2, max(mag_thick+10, airgap+10))
    ax.set_xlabel('tangential (mm)'); ax.set_ylabel('z (mm)')

    # Perspective (simple isometric)
    ax = axes[1,1]
    ax.set_title('Perspective (isometric)')
    # simple isometric perspective: draw disk edge thickness and magnet
    ax.text(0.08,0.7,'Magnet (red)', transform=ax.transAxes, color='C1')
    ax.text(0.08,0.55,'Sensor (green) at 5 mm inboard', transform=ax.transAxes, color='C2')
    # draw a schematic disk edge (1/8" = steel_back_thickness mm)
    disk_edge_w = 40
    disk_edge_h = steel_back_thickness
    # draw steel disk from z = -disk_edge_h .. 0 so upper face is at z=0
    ax.add_patch(Rectangle((10, -disk_edge_h), disk_edge_w, disk_edge_h, color='0.2', alpha=0.6))
    # draw magnet sitting on top of disk (magnet lower face at z=0)
    ax.add_patch(Rectangle((10+disk_edge_w+8, 0), mag_radial*0.6, mag_thick*0.6, color='C1', alpha=0.9))
    # sensor positioned above magnet top face by airgap (visual scale)
    persp_sensor_y = 10 + 0 + mag_thick*0.6 + sensor_z*0.2
    ax.plot([10+disk_edge_w+8 + mag_radial*0.3], [persp_sensor_y], 'o', color='C2')
    ax.text(10+disk_edge_w+8 + mag_radial*0.3+4, persp_sensor_y, f'sensor z={sensor_z:.1f} mm', color='C2')
    ax.axis('off')

    plt.tight_layout()
    os.makedirs(outdir, exist_ok=True)
    svgpath = os.path.join(outdir,'sensor_diagram.png')
    fig.savefig(svgpath, dpi=150)
    print('Wrote', svgpath)

def main():
    cfg = yaml.safe_load(open('examples/configs/n52_20x8x1.5_60_outer4in_sensor3p8in_fine.yaml'))
    draw(cfg, 'examples/plots')

if __name__ == '__main__':
    main()
