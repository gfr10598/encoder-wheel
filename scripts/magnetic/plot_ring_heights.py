#!/usr/bin/env python3
"""
Generate field plots for 60-magnet ring at multiple heights.

Sweeps sensor theta around the fixed magnet ring (4 full cycles, 480 points total).
Plots Bz (axial) and By (tangential) components at each height 1-8 mm.
"""

import sys
import os
import math
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from magnetic.magnet import MagnetCorners, Magnet
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def create_60magnet_ring(outer_radius_mm=101.6, magnet_dims_mm=(20.0, 8.0, 1.5), n_magnets=60):
    """Create magnets in a ring configuration.
    
    Args:
        outer_radius_mm: outer radius of ring
        magnet_dims_mm: [L, W, T] magnet dimensions in mm
        n_magnets: number of magnets in the full ring
    
    Returns:
        list of Magnet objects positioned in ring
    """
    L, W, T = magnet_dims_mm
    
    # Magnet center radius: outer_radius - radial half-length
    r_center = outer_radius_mm - L / 2.0
    
    magnets = []
    for i in range(n_magnets):
        theta_rad = 2 * math.pi * i / n_magnets
        x = r_center * math.cos(theta_rad)
        y = r_center * math.sin(theta_rad)
        
        # Alternate poles: mu = 1.0 for N-pole (+Z), -1.0 for S-pole (-Z)
        mu = 1.0 if (i % 2 == 0) else -1.0
        mag = Magnet(mx=L, my=W, mz=T, mu=mu)
        mag.theta_rad = theta_rad
        mag.x_mm = x
        mag.y_mm = y
        mag.z_mm = T / 2.0  # Magnet center at half its thickness (bottom at z=0)
        
        magnets.append(mag)
    
    return magnets


def compute_field_at_sensor(magnets, sensor_theta_rad, sensor_radius_mm, height_mm, magnet_thickness_mm=1.5, Br_T=1.45):
    """Compute Bz and By at sensor position.
    
    Args:
        magnets: list of Magnet objects
        sensor_theta_rad: sensor angle in radians
        sensor_radius_mm: radial distance from disk center
        height_mm: height above magnet top surface
        magnet_thickness_mm: thickness of magnets
        Br_T: remanent flux density
    
    Returns:
        (Bz_gauss, Br_gauss, Btheta_gauss)
    """
    sensor_x = sensor_radius_mm * math.cos(sensor_theta_rad)
    sensor_y = sensor_radius_mm * math.sin(sensor_theta_rad)
    sensor_z = magnet_thickness_mm + height_mm
    
    sensor_pos = np.array([sensor_x, sensor_y, sensor_z])
    
    B_total = np.zeros(3)
    
    for mag in magnets:
        # Magnet center position
        magnet_center = np.array([mag.x_mm, mag.y_mm, mag.z_mm])
        magnet_dims = np.array([mag.mx, mag.my, mag.mz])
        
        # Compute field at sensor using Aharoni formula
        # Pass Br_T * mu so S-poles (mu=-1) have negative Br_T
        B_field = MagnetCorners.compute_field_analytic(
            magnet_center,
            magnet_dims,
            sensor_pos,
            Br_T=Br_T * mag.mu
        )
        
        B_total += B_field
    
    # Convert to Gauss
    Bz_gauss = B_total[2] * 10000.0
    
    # Transform Cartesian to cylindrical coordinates at sensor position
    # Br (radial) = Bx * cos(theta) + By * sin(theta)
    # Btheta (tangential) = -Bx * sin(theta) + By * cos(theta)
    Br = B_total[0] * math.cos(sensor_theta_rad) + B_total[1] * math.sin(sensor_theta_rad)
    Btheta = -B_total[0] * math.sin(sensor_theta_rad) + B_total[1] * math.cos(sensor_theta_rad)
    
    Br_gauss = Br * 10000.0
    Btheta_gauss = Btheta * 10000.0
    
    return Bz_gauss, Br_gauss, Btheta_gauss


def main():
    """Generate field plots for magnet ring."""
    parser = argparse.ArgumentParser(description='Magnet ring field plots')
    parser.add_argument('config_dir',
                        help='Directory containing config.json')
    args = parser.parse_args()

    config_path = os.path.join(args.config_dir, 'config.json')
    with open(config_path) as f:
        cfg = json.load(f)

    n_magnets      = cfg['n_magnets']
    outer_radius   = cfg['outer_radius_mm']
    magnet_dims    = tuple(cfg['magnet_dims_mm'])
    sensor_radius_mm = cfg['sensor_radius_mm']
    heights_mm     = cfg['plot_heights_mm']
    Br_T           = cfg['Br_T']
    sweep_deg_cfg  = cfg.get('sweep_deg', 24.0)

    out_dir = os.path.dirname(os.path.abspath(config_path))
    L, W, T = magnet_dims
    print(f"Config: {config_path}")
    print(f"Creating {n_magnets}-magnet ring configuration...")
    magnets = create_60magnet_ring(outer_radius_mm=outer_radius, magnet_dims_mm=magnet_dims, n_magnets=n_magnets)

    # K&J on-axis cross-check: single 20×8×1.5mm magnet, sensor 8mm above surface
    # Compare to K&J reference result (user to verify at kjmagnetics.com/fieldcalc.asp)
    r_center = 101.6 - L / 2.0  # 91.6 mm
    mag_center_onaxis = [r_center, 0.0, T / 2]
    sensor_onaxis = [r_center, 0.0, T + 8.0]  # directly above center
    B_onaxis = MagnetCorners.compute_field_analytic(
        mag_center_onaxis, [L, W, T], sensor_onaxis, Br_T=Br_T)
    print(f"K&J cross-check — single {L:.0f}×{W:.0f}×{T:.1f}mm N52, 8mm above surface (on-axis):")
    print(f"  Bz = {B_onaxis[2]*1e4:.1f} G  (check against kjmagnetics.com/fieldcalc.asp)")
    print()

    # sweep_deg from config (default 24°), 10 pts/degree
    sweep_deg = sweep_deg_cfg
    n_points = int(sweep_deg * 10)
    theta_degrees = np.linspace(0, sweep_deg, n_points, endpoint=False)
    theta_radians = np.radians(theta_degrees)

    print(f"Sweeping sensor at {sensor_radius_mm} mm radius over {sweep_deg}° ({n_points} points)...")
    
    # Compute field at all heights
    for height_mm in heights_mm:
        print(f"\n  Height {height_mm} mm...", end=" ", flush=True)
        
        Bz_data = []
        Br_data = []
        Btheta_data = []
        
        for theta_rad in theta_radians:
            Bz, Br, Btheta = compute_field_at_sensor(magnets, theta_rad, sensor_radius_mm, height_mm)
            Bz_data.append(Bz)
            Br_data.append(Br)
            Btheta_data.append(Btheta)
        
        print(f"peak Bz={max(Bz_data):.1f}G, peak Br={max(Br_data):.1f}G, peak Bθ={max(Btheta_data):.1f}G")
        
        # Create plot
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10))
        
        # Bz (axial) plot
        ax1.plot(theta_degrees, Bz_data, 'b-', linewidth=1.5, label=f'Bz (axial)')
        ax1.axhline(0, color='k', linestyle='-', alpha=0.3, linewidth=0.5)
        ax1.grid(True, alpha=0.3)
        ax1.set_ylabel('Bz (Gauss)', fontsize=11)
        ax1.set_title(f'60-Magnet Ring: Cylindrical Field Components at Height {height_mm} mm  (24° sweep)', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper right')
        
        # Br (radial) plot
        ax2.plot(theta_degrees, Br_data, 'g-', linewidth=1.5, label=f'Br (radial)')
        ax2.axhline(0, color='k', linestyle='-', alpha=0.3, linewidth=0.5)
        ax2.grid(True, alpha=0.3)
        ax2.set_ylabel('Br (Gauss)', fontsize=11)
        ax2.legend(loc='upper right')
        
        # Btheta (tangential) plot
        ax3.plot(theta_degrees, Btheta_data, 'r-', linewidth=1.5, label=f'Bθ (tangential)')
        ax3.axhline(0, color='k', linestyle='-', alpha=0.3, linewidth=0.5)
        ax3.grid(True, alpha=0.3)
        ax3.set_xlabel('Sensor Angle (degrees)', fontsize=11)
        ax3.set_ylabel('Bθ (Gauss)', fontsize=11)
        ax3.legend(loc='upper right')
        
        plt.tight_layout()
        
        os.makedirs(out_dir, exist_ok=True)
        
        height_str = f"{height_mm:.1f}".replace('.', 'p')
        filename = os.path.join(out_dir, f"{n_magnets}mag_ring_height_{height_str}mm.png")
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"    → {filename}")
        
        plt.close()
    
    print("\n✓ All plots generated")


if __name__ == '__main__':
    main()
