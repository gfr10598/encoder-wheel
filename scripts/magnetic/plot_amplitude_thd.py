#!/usr/bin/env python3
"""
Amplitude and THD vs airgap height for the 60-magnet ring.

For each height, sweeps 24° (2 full N-S cycles), computes FFT of
Bz, Br, and Bθ, extracts the fundamental amplitude and THD.
"""

import sys, os, math, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from plot_ring_heights import create_60magnet_ring, compute_field_at_sensor


def save_amplitude_thd_plot(heights_mm, amps, thd, title, fpath, ylim=None,
                            xlabel='Airgap height (mm)', unit='Gauss'):
    """Save a 2-panel amplitude + THD vs airgap figure to *fpath*."""    
    colors = {'Bz': 'tab:blue', 'Br': 'tab:green', 'Btheta': 'tab:orange'}
    labels_map = {'Bz': 'Bz (axial)', 'Br': 'Br (radial)', 'Btheta': 'Bθ (tangential)'}

    fig, (ax_amp, ax_thd) = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
    fig.suptitle(title, fontsize=13)

    for key in ('Bz', 'Btheta', 'Br'):
        ax_amp.plot(heights_mm, amps[key], marker='o', markersize=4,
                    color=colors[key], label=labels_map[key])
        ax_thd.plot(heights_mm, thd[key],  marker='o', markersize=4,
                    color=colors[key], label=labels_map[key])

    ax_amp.set_ylabel(f'Fundamental amplitude ({unit} peak)')
    ax_amp.set_yscale('log')
    ax_amp.legend()
    ax_amp.grid(True, which='both', alpha=0.3)
    ax_amp.set_title('Amplitude')

    ax_thd.set_xlabel(xlabel)
    ax_thd.set_ylabel('THD (%)')
    ax_thd.set_yscale('log')
    if ylim is not None:
        ax_thd.set_ylim(*ylim)
    ax_thd.legend()
    ax_thd.grid(True, which='both', alpha=0.3)
    ax_thd.set_title('Total Harmonic Distortion')

    plt.tight_layout()
    os.makedirs(os.path.dirname(os.path.abspath(fpath)), exist_ok=True)
    plt.savefig(fpath, dpi=120)
    plt.close()
    print(f"Saved {fpath}")


def main():
    parser = argparse.ArgumentParser(description='Magnet ring amplitude/THD vs airgap')
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
    heights_mm     = np.array(cfg['thd_heights_mm'])
    sweep_deg      = cfg.get('sweep_deg', 24.0)

    # 20 pts/degree; fundamental at FFT bin 2 (2 full cycles in window)
    n_points  = int(sweep_deg * 20)
    FUND_BIN  = 2
    theta_deg_arr = np.linspace(0, sweep_deg, n_points, endpoint=False)
    theta_rad_arr = np.radians(theta_deg_arr)

    # ── Build ring ────────────────────────────────────────────────────────────
    print(f"Config: {config_path}")
    print(f"Building {n_magnets}-magnet ring...")
    magnets = create_60magnet_ring(outer_radius_mm=outer_radius, magnet_dims_mm=magnet_dims, n_magnets=n_magnets)

    # ── Sweep and analyse ─────────────────────────────────────────────────────
    amps = {'Bz': [], 'Br': [], 'Btheta': []}
    thd  = {'Bz': [], 'Br': [], 'Btheta': []}

    for h in heights_mm:
        Bz_arr, Br_arr, Bt_arr = [], [], []
        for tr in theta_rad_arr:
            bz, br, bt = compute_field_at_sensor(magnets, tr, sensor_radius_mm, h)
            Bz_arr.append(bz); Br_arr.append(br); Bt_arr.append(bt)

        for label, data in [('Bz', Bz_arr), ('Br', Br_arr), ('Btheta', Bt_arr)]:
            spectrum = np.abs(np.fft.rfft(data)) / n_points
            amp_spectrum = spectrum.copy()
            amp_spectrum[1:-1] *= 2
            fund = amp_spectrum[FUND_BIN]
            harmonics = amp_spectrum[FUND_BIN + 1:]
            thd_val = 100.0 * np.sqrt(np.sum(harmonics**2)) / (fund + 1e-30)
            amps[label].append(fund)
            thd[label].append(thd_val)
        print(f"  h={h:.1f} mm  Bz={amps['Bz'][-1]:.1f}G  Bθ={amps['Btheta'][-1]:.1f}G  "
              f"THD_Bz={thd['Bz'][-1]:.2f}%  THD_Bθ={thd['Btheta'][-1]:.2f}%")

    out_dir = os.path.dirname(os.path.abspath(config_path))
    fpath = os.path.join(out_dir, f'{n_magnets}mag_amplitude_thd.png')
    save_amplitude_thd_plot(
        heights_mm, amps, thd,
        f'{n_magnets}-Magnet Ring: Fundamental Amplitude and THD vs Airgap',
        fpath, ylim=(0.05, 20.0)
    )


if __name__ == '__main__':
    main()

