#!/usr/bin/env python3
"""
Field sweep plots and amplitude/THD analysis for the 4-magnet symmetric cross.

Generates two outputs in the config directory:
  4magnet_heights.png      — Br/Bθ/Bz vs angle at each height in heights_mm
  4magnet_amplitude_thd.png — fundamental amplitude and THD vs airgap (thd_heights_mm)
"""

import sys, os, math, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from magnet import MagnetCorners
from plot_amplitude_thd import save_amplitude_thd_plot

# 20 pts/degree × 360° = 7200; fundamental bin derived from n_magnets in config
_THD_N_POINTS = 7200


def field_at(sensor_pos, magnets):
    B = np.zeros(3)
    for m in magnets:
        B += MagnetCorners.compute_field_analytic(m['center'], m['dims'], sensor_pos, Br_T=m['Br_T'])
    return B


def sweep(magnets, sensor_radius_mm, sensor_z_mm, n_points=360):
    thetas = np.linspace(0, 2 * math.pi, n_points, endpoint=False)
    Br_arr = np.zeros(n_points)
    Bt_arr = np.zeros(n_points)
    Bz_arr = np.zeros(n_points)

    for i, th in enumerate(thetas):
        sx = sensor_radius_mm * math.cos(th)
        sy = sensor_radius_mm * math.sin(th)
        B = field_at([sx, sy, sensor_z_mm], magnets)
        Br_arr[i] = ( B[0] * math.cos(th) + B[1] * math.sin(th))
        Bt_arr[i] = (-B[0] * math.sin(th) + B[1] * math.cos(th))
        Bz_arr[i] = B[2]

    return np.degrees(thetas), Br_arr * 1e3, Bt_arr * 1e3, Bz_arr * 1e3   # → mT


def _fft_amp_thd(signal, n_points, fund_bin):
    spectrum = np.abs(np.fft.rfft(signal)) / n_points
    amp_spectrum = spectrum.copy()
    amp_spectrum[1:-1] *= 2
    fund      = amp_spectrum[fund_bin]
    harmonics = amp_spectrum[fund_bin + 1:]
    thd_val   = 100.0 * np.sqrt(np.sum(harmonics**2)) / (fund + 1e-30)
    return fund, thd_val


def plot_heights(magnets, sensor_radius_mm, T, heights_mm, out_dir):
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    fig.suptitle(f"4-magnet cross — r={sensor_radius_mm} mm, heights {heights_mm[0]}–{heights_mm[-1]} mm above surface", fontsize=12)

    cmap = plt.cm.plasma
    colors = [cmap(i / (len(heights_mm) - 1)) for i in range(len(heights_mm))]

    for z_mm, color in zip(heights_mm, colors):
        degs, Br, Bt, Bz = sweep(magnets, sensor_radius_mm, T + z_mm)
        for ax, values in zip(axes, [Br, Bt, Bz]):
            ax.plot(degs, values, color=color, label=f"{z_mm} mm")

    labels = ['Br (radial)', 'Bθ (tangential)', 'Bz (axial)']
    for ax, label in zip(axes, labels):
        ax.axhline(0, color='k', linewidth=0.5, linestyle='--')
        ax.set_ylabel(f"{label} [mT]")
        ax.grid(True, alpha=0.3)
        for ang in [0, 90, 180, 270]:
            ax.axvline(ang, color='gray', linestyle=':', linewidth=0.8)

    axes[-1].set_xlabel('Sensor angle (deg)')
    axes[0].set_xticks(range(0, 361, 45))
    axes[0].legend(title='Airgap', loc='upper right', fontsize=8, ncol=2)

    plt.tight_layout()
    fpath = os.path.join(out_dir, '4magnet_heights.png')
    plt.savefig(fpath, dpi=120)
    plt.close()
    print(f"Saved {fpath}")


def plot_amplitude_thd(magnets, sensor_radius_mm, T, thd_heights_mm, fund_bin, out_dir):
    thetas = np.linspace(0, 2 * math.pi, _THD_N_POINTS, endpoint=False)
    amps = {'Bz': [], 'Br': [], 'Btheta': []}
    thd  = {'Bz': [], 'Br': [], 'Btheta': []}

    for h in thd_heights_mm:
        sensor_z = T + h
        Br_arr = np.zeros(_THD_N_POINTS)
        Bt_arr = np.zeros(_THD_N_POINTS)
        Bz_arr = np.zeros(_THD_N_POINTS)
        for i, th in enumerate(thetas):
            sx = sensor_radius_mm * math.cos(th)
            sy = sensor_radius_mm * math.sin(th)
            B = field_at([sx, sy, sensor_z], magnets)
            Br_arr[i] = ( B[0] * math.cos(th) + B[1] * math.sin(th)) * 1e4  # Gauss
            Bt_arr[i] = (-B[0] * math.sin(th) + B[1] * math.cos(th)) * 1e4
            Bz_arr[i] = B[2] * 1e4

        for label, data in [('Bz', Bz_arr), ('Br', Br_arr), ('Btheta', Bt_arr)]:
            amp, thd_val = _fft_amp_thd(data, _THD_N_POINTS, fund_bin)
            amps[label].append(amp)
            thd[label].append(thd_val)
        print(f"  h={h:5.1f} mm  Bz={amps['Bz'][-1]:7.1f}G  Bθ={amps['Btheta'][-1]:7.1f}G  "
              f"THD_Bz={thd['Bz'][-1]:.2f}%  THD_Bθ={thd['Btheta'][-1]:.2f}%")

    fpath = os.path.join(out_dir, '4magnet_amplitude_thd.png')
    save_amplitude_thd_plot(
        np.array(thd_heights_mm), amps, thd,
        '4-Magnet Cross: Fundamental Amplitude and THD vs Airgap',
        fpath
    )


def main():
    parser = argparse.ArgumentParser(description='4-magnet cross field plots and THD analysis')
    parser.add_argument('config_dir', help='Directory containing config.json')
    args = parser.parse_args()

    config_path = os.path.join(args.config_dir, 'config.json')
    with open(config_path) as f:
        cfg = json.load(f)

    magnet_dims      = cfg['magnet_dims_mm']
    radius_mm        = cfg['radius_mm']
    z_center_mm      = cfg['z_center_mm']
    sensor_radius_mm = cfg['sensor_radius_mm']
    heights_mm       = cfg['heights_mm']
    thd_heights_mm   = cfg.get('thd_heights_mm', heights_mm)
    T                = magnet_dims[2]

    magnets = []
    for entry in cfg['magnets']:
        th = math.radians(entry['theta_deg'])
        magnets.append({
            'center': [radius_mm * math.cos(th), radius_mm * math.sin(th), z_center_mm],
            'dims':   magnet_dims,
            'Br_T':   entry['Br_T'],
        })

    n_magnets      = len(magnets)
    fund_bin       = cfg.get('fund_bin', n_magnets // 2)

    out_dir = os.path.dirname(os.path.abspath(config_path))
    os.makedirs(out_dir, exist_ok=True)
    print(f"Config: {config_path}")

    plot_heights(magnets, sensor_radius_mm, T, heights_mm, out_dir)
    plot_amplitude_thd(magnets, sensor_radius_mm, T, thd_heights_mm, fund_bin, out_dir)


if __name__ == '__main__':
    main()

