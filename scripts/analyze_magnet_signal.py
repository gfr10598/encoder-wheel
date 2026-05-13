#!/usr/bin/env python3
import os, sys, math, json, argparse
import numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
from analysis_utils import compute_field_from_magnets
from coords import cyl_to_cart
from scripts.common_config import load_config, validate_config

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
        # set center z so the magnet's large face sits at z=0 (disk top)
        mz = magnet_dims[2] / 2.0
        mags.append({'center': [x,y,0.0], 'dims': magnet_dims, 'axis': axis_vec, 'Br': Br})
    return mags

def run_sim(cfg):
    n = cfg['n_magnets']
    outer = cfg['outer_radius_mm']
    # place sensor by default 5 mm inboard from the magnet outer face
    sensor_offset_from_outer = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
    magnet_dims = cfg['magnet_dims_mm']
    Br = cfg.get('Br_T', 1.45)
    airgaps = np.linspace(cfg['airgap_min_mm'], cfg['airgap_max_mm'], cfg.get('airgap_steps',8))
    theta_steps = cfg.get('theta_steps',1024)
    model = cfg.get('model','dipole')
    discrete_grid = tuple(cfg.get('discrete_grid',(1,1)))
    r_inner = outer - magnet_dims[0]
    mags = build_ring_config(n, r_inner, magnet_dims, Br=Br)
    mz = magnet_dims[2] / 2.0
    for m in mags:
        m['center'][2] = mz
    # optional window: number of pole pairs to include around sensor (total magnets = 2*pole_pairs)
    pole_pairs_window = cfg.get('pole_pairs_window', None)
    if pole_pairs_window is not None:
        try:
            pole_pairs_window = int(pole_pairs_window)
        except Exception:
            pole_pairs_window = None
    results = []
    outdir = cfg.get('outdir','examples/plots')
    os.makedirs(outdir, exist_ok=True)
    for ag in airgaps:
        # sensor z measured from magnet top face: magnet_top = magnet_thickness
        sensor_z = (magnet_dims[2] + ag)/1000.0
        sensor_theta_deg = float(cfg.get('sensor_theta_deg', 0.0))
        sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
        sensor_pos = cyl_to_cart(sensor_r/1000.0, math.radians(sensor_theta_deg), sensor_z)
        thetas = np.linspace(0,2*math.pi,theta_steps,endpoint=False)
        bx = np.zeros_like(thetas)
        by = np.zeros_like(thetas)
        bz = np.zeros_like(thetas)
        pitch = 2*math.pi / n
        for idx, th in enumerate(thetas):
            rotated_centers = []
            if pole_pairs_window is None:
                sel_indices = range(n)
            else:
                total_mags = int(pole_pairs_window) * 2
                half_span = total_mags // 2
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
                mm = dict(m)
                mm['center'] = cr
                mm['axis'] = (float(ar[0]), float(ar[1]), float(ar[2]))
                rotated_centers.append(mm)
            # use cylindrical sensor coordinates (R, theta_deg, Z) -> Cartesian
            B = compute_field_from_magnets(rotated_centers, sensor_pos, model=model, Br=Br, discrete_grid=discrete_grid, steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
            bx[idx] = B[0]; by[idx] = B[1]; bz[idx] = B[2]
        complex_signal = np.ascontiguousarray(np.array(bx, dtype=np.float64) + 1j * np.array(by, dtype=np.float64), dtype=np.complex128)
        # per-channel FFTs
        N = len(complex_signal)
        fft_c = np.fft.fft(complex_signal)
        amps_c = np.abs(fft_c)/N
        fft_bx = np.fft.fft(bx)
        amps_bx = np.abs(fft_bx)/N
        fft_by = np.fft.fft(by)
        amps_by = np.abs(fft_by)/N
        # correct fundamental index: number of pole-pairs = n/2
        fund_idx = max(1, n//2)
        fundamental_c = amps_c[fund_idx] if len(amps_c)>fund_idx else 0.0
        fundamental_bx = amps_bx[fund_idx] if len(amps_bx)>fund_idx else 0.0
        fundamental_by = amps_by[fund_idx] if len(amps_by)>fund_idx else 0.0
        thd = 100.0 * np.sqrt(np.sum(amps_c[fund_idx+1:]**2)) / (fundamental_c + 1e-30)

        # symmetry checks
        checks = {}
        # DC should be near zero
        checks['mean_bx'] = float(np.mean(bx))
        checks['mean_by'] = float(np.mean(by))
        checks['mean_bz'] = float(np.mean(bz))
        # peak symmetry for tangential field
        max_bx = float(np.max(bx))
        min_bx = float(np.min(bx))
        checks['peak_symmetry_bx'] = abs(max_bx - abs(min_bx)) / (max(abs(max_bx), abs(min_bx)) + 1e-30)
        # perpendicular inversion across adjacent magnets: sample at magnet centers
        sample_idxs = (np.linspace(0, N, n, endpoint=False)).astype(int)
        bz_at_mags = bz[sample_idxs]
        inv_diffs = []
        for i in range(len(bz_at_mags)//2):
            a = bz_at_mags[2*i]
            b = bz_at_mags[(2*i+1) % len(bz_at_mags)]
            inv_diffs.append(abs(a + b) / (max(abs(a), abs(b)) + 1e-30))
        checks['perp_inv_mean_rel'] = float(np.mean(inv_diffs)) if inv_diffs else 0.0

        results.append({'airgap_mm': float(ag), 'amp_fund_mT': float(fundamental_c*1e3), 'amp_fund_bx_mT': float(fundamental_bx*1e3), 'amp_fund_by_mT': float(fundamental_by*1e3), 'thd_pct': float(thd), 'checks': checks})
        # plot raw signals in mT for quick visual check
        plt.figure(figsize=(8,4))
        plt.plot(np.degrees(thetas), bx*1e3, label='Bx')
        plt.plot(np.degrees(thetas), by*1e3, label='By')
        plt.xlabel('theta (deg)'); plt.legend(); plt.title(f'airgap {ag} mm')
        plt.tight_layout()
        plt.savefig(os.path.join(outdir,f'raw_B_{int(ag*100)}.png'))
        plt.close()
    summary_path = cfg.get('summary_path', os.path.join(outdir,'summary.json'))
    with open(summary_path,'w') as f:
        json.dump(results,f,indent=2)
    print('Done. Summary written to', summary_path)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    args = p.parse_args()
    cfg = load_config(args.config)
    validate_config(cfg, ['n_magnets', 'outer_radius_mm', 'magnet_dims_mm'])
    run_sim(cfg)

if __name__ == '__main__':
    main()
