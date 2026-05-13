#!/usr/bin/env python3
"""Plot combined sine/cosine overlays and amp/THD vs airgap from simulation.

Usage: python scripts/plot_results.py --config examples/configs/....yaml
"""
import os
import sys
import math
import json
import argparse
import yaml, numpy as np, math
import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from analysis_utils import compute_field_from_magnets
from coords import cyl_to_cart

def build_ring_config(n_magnets, r_inner, magnet_dims, Br=1.45):
    r_center = r_inner + magnet_dims[0]/2.0
    mags = []
    for i in range(n_magnets):
        theta = 2*math.pi*i/n_magnets
        x = r_center*math.cos(theta)
        y = r_center*math.sin(theta)
        # poles through faces: axis perpendicular to disk (z); alternate polarity
        polarity = -1.0 if (i % 2) else 1.0
        axis_vec = (0.0, 0.0, polarity)
        # center z will be set so the magnet's large face sits at z=0 by callers
        mags.append({'center': [x,y,0.0], 'dims': magnet_dims, 'axis': axis_vec, 'Br': Br})
    return mags

def overlay_signals(cfg, airgaps_mm, outdir):
    n = cfg['n_magnets']
    outer = cfg['outer_radius_mm']
    sensor_offset_from_outer = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
    magnet_dims = cfg['magnet_dims_mm']
    Br = cfg.get('Br_T', 1.45)
    theta_steps = cfg.get('theta_steps', 2048)
    model = cfg.get('model','dipole')
    discrete_grid = tuple(cfg.get('discrete_grid',(1,1,1)))
    pole_pairs_window = cfg.get('pole_pairs_window', None)
    if pole_pairs_window is not None:
        try:
            pole_pairs_window = int(pole_pairs_window)
        except Exception:
            pole_pairs_window = None
    r_inner = outer - magnet_dims[0]
    mags = build_ring_config(n, r_inner, magnet_dims, Br=Br)
    mz = magnet_dims[2] / 2.0
    for m in mags:
        m['center'][2] = mz
    thetas = np.linspace(0,2*math.pi,theta_steps,endpoint=False)

    plt.figure(figsize=(9,4))
    window_deg = cfg.get('window_deg', 36)
    for ag in airgaps_mm:
        # sensor z measured from magnet top face: magnet top = magnet_thickness
        sensor_z = (magnet_dims[2] + ag)/1000.0
        sensor_theta_deg = float(cfg.get('sensor_theta_deg', 0.0))
        sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
        bx = np.zeros_like(thetas)
        for idx, th in enumerate(thetas):
            # optionally select local window of magnets
            rotated = []
            if pole_pairs_window is None:
                sel_indices = range(n)
            else:
                total_mags = int(pole_pairs_window) * 2
                half_span = total_mags // 2
                pitch = 2*math.pi / n
                center_idx = int(round((-th) / pitch)) % n
                start = center_idx - half_span
                end = center_idx + half_span - 1
                sel_indices = [(i % n) for i in range(start, end+1)]
            for mi in sel_indices:
                m = mags[mi]
                c = np.array(m['center'])
                cr = np.array([c[0]*math.cos(th)-c[1]*math.sin(th), c[0]*math.sin(th)+c[1]*math.cos(th), c[2]])
                a = np.array(m['axis'])
                ar = np.array([a[0]*math.cos(th)-a[1]*math.sin(th), a[0]*math.sin(th)+a[1]*math.cos(th), a[2]])
                mm = dict(m); mm['center']=cr; mm['axis']=(float(ar[0]), float(ar[1]), float(ar[2])); rotated.append(mm)
            sensor_pos = cyl_to_cart(sensor_r/1000.0, math.radians(sensor_theta_deg), sensor_z)
            B = compute_field_from_magnets(rotated, sensor_pos, model=model, Br=Br, discrete_grid=discrete_grid, steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
            bx[idx] = B[0]*1e3
        degs = np.degrees(thetas)
        mask = (degs >= 0) & (degs <= window_deg)
        plt.plot(degs[mask], bx[mask], label=f'{ag} mm')
    plt.xlabel('theta (deg)'); plt.ylabel('Bx (mT)'); plt.title('Overlay: sine (Bx) for airgaps')
    plt.legend(); plt.tight_layout()
    plt.savefig(os.path.join(outdir,'overlay_sine_airgaps.png'))
    plt.close()

    plt.figure(figsize=(9,4))
    for ag in airgaps_mm:
        sensor_z = (magnet_dims[2] + ag)/1000.0
        by = np.zeros_like(thetas)
        for idx, th in enumerate(thetas):
            rotated = []
            if pole_pairs_window is None:
                sel_indices = range(n)
            else:
                total_mags = int(pole_pairs_window) * 2
                half_span = total_mags // 2
                pitch = 2*math.pi / n
                center_idx = int(round((-th) / pitch)) % n
                start = center_idx - half_span
                end = center_idx + half_span - 1
                sel_indices = [(i % n) for i in range(start, end+1)]
            for mi in sel_indices:
                m = mags[mi]
                c = np.array(m['center'])
                cr = np.array([c[0]*math.cos(th)-c[1]*math.sin(th), c[0]*math.sin(th)+c[1]*math.cos(th), c[2]])
                a = np.array(m['axis'])
                ar = np.array([a[0]*math.cos(th)-a[1]*math.sin(th), a[0]*math.sin(th)+a[1]*math.cos(th), a[2]])
                mm = dict(m); mm['center']=cr; mm['axis']=(float(ar[0]), float(ar[1]), float(ar[2])); rotated.append(mm)
            sensor_pos = cyl_to_cart(sensor_r/1000.0, math.radians(sensor_theta_deg), sensor_z)
            B = compute_field_from_magnets(rotated, sensor_pos, model=model, Br=Br, discrete_grid=discrete_grid, steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
            by[idx] = B[1]*1e3
        degs = np.degrees(thetas)
        mask = (degs >= 0) & (degs <= window_deg)
        plt.plot(degs[mask], by[mask], label=f'{ag} mm')
    plt.xlabel('theta (deg)'); plt.ylabel('By (mT)'); plt.title('Overlay: cosine (By) for airgaps')
    plt.legend(); plt.tight_layout()
    plt.savefig(os.path.join(outdir,'overlay_cosine_airgaps.png'))
    plt.close()

def plot_amp_thd(summary_path, outdir):
    with open(summary_path,'r') as f:
        data = json.load(f)
    ag = [d['airgap_mm'] for d in data]
    amp = [d['amp_fund_mT']/1e3 for d in data]
    thd = [d['thd_pct'] for d in data]
    fig, ax1 = plt.subplots(figsize=(7,4))
    ax1.plot(ag, np.array(amp)*1e3, 'b-o', label='Fundamental amp (mT)')
    ax1.set_xlabel('airgap (mm)')
    ax1.set_ylabel('Fundamental amplitude (mT)', color='b')
    ax2 = ax1.twinx()
    ax2.plot(ag, thd, 'r-s', label='THD (%)')
    ax2.set_ylabel('THD (%)', color='r')
    plt.title('Field amplitude and THD vs airgap')
    fig.tight_layout()
    plt.savefig(os.path.join(outdir,'amp_thd_vs_airgap.png'))
    plt.close()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    p.add_argument('--airgaps', nargs='+', type=float, default=[2.0,4.0,6.0,8.0])
    args = p.parse_args()
    from scripts.common_config import load_config, validate_config
    cfg = load_config(args.config)
    validate_config(cfg, ['outer_radius_mm', 'magnet_dims_mm'])
    outdir = cfg.get('outdir','examples/plots')
    os.makedirs(outdir, exist_ok=True)
    # plot overlays (recompute signals for requested airgaps)
    overlay_signals(cfg, args.airgaps, outdir)
    # plot amp/thd vs airgap from summary
    summary = cfg.get('summary_path', os.path.join(outdir,'summary.json'))
    if os.path.exists(summary):
        plot_amp_thd(summary, outdir)
    else:
        print('Warning: summary JSON not found at', summary)

if __name__ == '__main__':
    main()
