#!/usr/bin/env python3
"""
Field plots for a radially-magnetized arc magnet ring.

Each arc magnet is approximated as n_subblocks rectangular sub-blocks, each
with magnetization pointing along the local radial direction (±X in the prism's
local frame).  Uses MagnetCornersVec which supports arbitrary Br direction.

Sensor sweeps at fixed radii *outside* the ring in the mid-plane (z = axial/2).

Config keys (in addition to n_magnets, Br_T, sweep_deg):
    outer_radius_mm   -- outer radius of magnet arc (mm)
    inner_radius_mm   -- inner radius of magnet arc (mm)
    arc_deg           -- angular span of each magnet (degrees)
    magnet_axial_mm   -- axial height of magnets (mm)
    n_subblocks       -- rectangular sub-blocks per magnet (default 8)
    plot_radii_mm     -- list of sensor radii for per-radius sweep plots
    thd_radii_mm      -- list of sensor radii for amplitude/THD analysis
"""

import sys
import os
import math
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from magnet_vec import MagnetCornersVec
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from plot_amplitude_thd import save_amplitude_thd_plot


def build_arc_ring_subblocks(n_magnets, outer_r_mm, inner_r_mm, arc_deg,
                              axial_mm, Br_T, n_subblocks=8):
    """Build flat list of sub-block descriptors for all arc magnets.

    Each arc magnet is decomposed into n_subblocks rectangular prisms.
    Polarity alternates N/S between magnets.

    Returns:
        list of dicts: {center_mm, dims_mm, Br_vec_local}
    """
    r_center    = (outer_r_mm + inner_r_mm) / 2.0
    radial_span = outer_r_mm - inner_r_mm
    z_center    = axial_mm / 2.0
    sub_span_deg = arc_deg / n_subblocks
    sub_width_mm = 2.0 * math.pi * r_center * (sub_span_deg / 360.0)
    dims = [radial_span, sub_width_mm, axial_mm]  # [L_radial, W_tang, T_axial]

    pitch_deg = 360.0 / n_magnets

    subblocks = []
    for i in range(n_magnets):
        theta_mag_deg = i * pitch_deg
        polarity = 1.0 if (i % 2 == 0) else -1.0
        Br_vec_local = [Br_T * polarity, 0.0, 0.0]  # radially outward / inward

        for j in range(n_subblocks):
            # Centre angle of this sub-block
            theta_sub_deg = theta_mag_deg + (j - (n_subblocks - 1) / 2.0) * sub_span_deg
            theta_sub_rad = math.radians(theta_sub_deg)
            cx = r_center * math.cos(theta_sub_rad)
            cy = r_center * math.sin(theta_sub_rad)
            subblocks.append({
                'center_mm':   [cx, cy, z_center],
                'dims_mm':     dims,
                'Br_vec_local': Br_vec_local,
            })

    return subblocks


def compute_field_arc(subblocks, sensor_theta_rad, sensor_radius_mm, sensor_z_mm):
    """Total field from all sub-blocks at sensor position.

    Returns:
        (Bz_gauss, Br_gauss, Btheta_gauss) in cylindrical coordinates.
    """
    sx = sensor_radius_mm * math.cos(sensor_theta_rad)
    sy = sensor_radius_mm * math.sin(sensor_theta_rad)
    sensor_pos = [sx, sy, sensor_z_mm]

    B_total = np.zeros(3)
    for sb in subblocks:
        B_total += MagnetCornersVec.compute_field_analytic(
            sb['center_mm'], sb['dims_mm'], sensor_pos, sb['Br_vec_local']
        )

    ct = math.cos(sensor_theta_rad)
    st = math.sin(sensor_theta_rad)
    Br_cyl     = B_total[0] * ct + B_total[1] * st
    Btheta_cyl = -B_total[0] * st + B_total[1] * ct
    Bz_cyl     = B_total[2]

    return Bz_cyl * 1e3, Br_cyl * 1e3, Btheta_cyl * 1e3  # T -> mT


def main():
    parser = argparse.ArgumentParser(description='Arc magnet ring field plots')
    parser.add_argument('config_dir', help='Directory containing config.json')
    args = parser.parse_args()

    config_path = os.path.join(args.config_dir, 'config.json')
    with open(config_path) as f:
        cfg = json.load(f)

    n_magnets    = cfg['n_magnets']
    outer_r      = cfg['outer_radius_mm']
    inner_r      = cfg['inner_radius_mm']
    arc_deg      = cfg['arc_deg']
    axial_mm     = cfg['magnet_axial_mm']
    n_subblocks  = cfg.get('n_subblocks', 8)
    Br_T         = cfg['Br_T']
    pts_n        = cfg.get('pts_n', 8)        # step = pitch / pts_n²
    plot_radii   = cfg['plot_radii_mm']
    thd_radii    = np.array(cfg['thd_radii_mm'])
    sensor_z_mm  = axial_mm / 2.0  # sensor in mid-plane of magnets

    pitch_deg = 360.0 / n_magnets
    sweep_deg = 4.0 * pitch_deg             # exactly 2 N-S cycles
    n_pts     = 4 * pts_n ** 2              # pts aligned to cycle boundaries

    out_dir = os.path.dirname(os.path.abspath(config_path))

    print(f"Config: {config_path}")
    print(f"Building {n_magnets}-magnet arc ring ({n_subblocks} sub-blocks each)...")
    subblocks = build_arc_ring_subblocks(
        n_magnets, outer_r, inner_r, arc_deg, axial_mm, Br_T, n_subblocks
    )
    print(f"  Total sub-blocks: {len(subblocks)}")
    print(f"  Sub-block dims: radial={outer_r-inner_r:.1f} mm, "
          f"tang={subblocks[0]['dims_mm'][1]:.3f} mm, axial={axial_mm:.1f} mm")

    # ── Per-radius sweep plots ────────────────────────────────────────────────
    theta_deg_arr = np.linspace(0, sweep_deg, n_pts, endpoint=False)
    theta_rad_arr = np.radians(theta_deg_arr)

    print(f"\nSweeping {sweep_deg:.3f}° ({n_pts} pts, step={sweep_deg/n_pts:.4f}°) at {len(plot_radii)} radii...")
    for r in plot_radii:
        print(f"  r={r} mm...", end=" ", flush=True)
        Bz_data, Br_data, Bt_data = [], [], []
        for tr in theta_rad_arr:
            bz, br, bt = compute_field_arc(subblocks, tr, r, sensor_z_mm)
            Bz_data.append(bz); Br_data.append(br); Bt_data.append(bt)
        pk_br = max(abs(v) for v in Br_data)
        pk_bt = max(abs(v) for v in Bt_data)
        print(f"peak Br={pk_br:.1f} mT  Bθ={pk_bt:.1f} mT")

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10))
        fig.suptitle(
            f'{n_magnets}-Magnet Arc Ring — sensor r={r} mm  '
            f'(ring OD={outer_r} mm, ID={inner_r} mm)',
            fontsize=12, fontweight='bold'
        )

        ax1.plot(theta_deg_arr, Bz_data, 'b-', linewidth=1.5)
        ax1.axhline(0, color='k', alpha=0.3, linewidth=0.5)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylabel('Bz (mT)')
        ax1.set_title('Bz (axial)')

        ax2.plot(theta_deg_arr, Br_data, 'g-', linewidth=1.5)
        ax2.axhline(0, color='k', alpha=0.3, linewidth=0.5)
        ax2.grid(True, alpha=0.3)
        ax2.set_ylabel('Br (mT)')
        ax2.set_title('Br (radial — encoder signal)')

        ax3.plot(theta_deg_arr, Bt_data, 'r-', linewidth=1.5)
        ax3.axhline(0, color='k', alpha=0.3, linewidth=0.5)
        ax3.grid(True, alpha=0.3)
        ax3.set_xlabel('Sensor Angle (degrees)')
        ax3.set_ylabel('Bθ (mT)')
        ax3.set_title('Bθ (tangential)')

        plt.tight_layout()
        fname = os.path.join(out_dir, f'{n_magnets}mag_arc_ring_radius_{r}mm.png')
        plt.savefig(fname, dpi=120)
        plt.close()
        print(f"    Saved {fname}")

    # ── Amplitude / THD vs sensor radius ─────────────────────────────────────
    n_pts_thd = n_pts   # same grid: 4*pts_n² points over exactly 2 cycles
    FUND_BIN  = 2       # fundamental always at bin 2 by construction
    theta_thd = np.radians(np.linspace(0, sweep_deg, n_pts_thd, endpoint=False))

    amps = {'Bz': [], 'Br': [], 'Btheta': []}
    thd  = {'Bz': [], 'Br': [], 'Btheta': []}

    print(f"\nAmplitude/THD sweep ({len(thd_radii)} radii, {n_pts_thd} pts each)...")
    for r in thd_radii:
        Bz_arr, Br_arr, Bt_arr = [], [], []
        for tr in theta_thd:
            bz, br, bt = compute_field_arc(subblocks, tr, r, sensor_z_mm)
            Bz_arr.append(bz); Br_arr.append(br); Bt_arr.append(bt)

        for label, data in [('Bz', Bz_arr), ('Br', Br_arr), ('Btheta', Bt_arr)]:
            spectrum = np.abs(np.fft.rfft(data)) / n_pts_thd
            amp_spec = spectrum.copy()
            amp_spec[1:-1] *= 2
            fund = amp_spec[FUND_BIN]
            harmonics = amp_spec[FUND_BIN + 1:]
            thd_val = 100.0 * np.sqrt(np.sum(harmonics**2)) / (fund + 1e-30)
            amps[label].append(fund)   # already in mT
            thd[label].append(thd_val)
        print(f"  r={r:.1f} mm  Br={amps['Br'][-1]:.1f} mT  "
              f"THD_Br={thd['Br'][-1]:.2f}%  THD_Bθ={thd['Btheta'][-1]:.2f}%")

    fpath = os.path.join(out_dir, f'{n_magnets}mag_amplitude_thd.png')
    save_amplitude_thd_plot(
        thd_radii, amps, thd,
        f'{n_magnets}-Magnet Arc Ring: Amplitude and THD vs Sensor Radius',
        fpath,
        xlabel='Sensor radius (mm)',
        unit='mT'
    )


if __name__ == '__main__':
    main()
