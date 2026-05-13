#!/usr/bin/env python3
import os, sys, math, json, yaml, argparse
import numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
from analysis_utils import compute_field_from_magnets

def build_ring_config(n_magnets, r_inner, magnet_dims, Br=1.45):
    r_center = r_inner + magnet_dims[0]/2.0
    mags = []
    for i in range(n_magnets):
        theta = 2*math.pi*i/n_magnets
        x = r_center*math.cos(theta)
        y = r_center*math.sin(theta)
        axis_vec = (math.cos(theta+math.pi/2), math.sin(theta+math.pi/2), 0)
        mags.append({'center': [x,y,0.0], 'dims': magnet_dims, 'axis': axis_vec, 'Br': Br})
    return mags

def run_sim(cfg):
    n = cfg['n_magnets']
    outer = cfg['outer_radius_mm']
    sensor_r = cfg['sensor_radius_mm']
    magnet_dims = cfg['magnet_dims_mm']
    Br = cfg.get('Br_T', 1.45)
    airgaps = np.linspace(cfg['airgap_min_mm'], cfg['airgap_max_mm'], cfg.get('airgap_steps',8))
    theta_steps = cfg.get('theta_steps',1024)
    model = cfg.get('model','dipole')
    discrete_grid = tuple(cfg.get('discrete_grid',(1,1)))
    r_inner = outer - magnet_dims[0]
    mags = build_ring_config(n, r_inner, magnet_dims, Br=Br)
    results = []
    outdir = cfg.get('outdir','examples/plots')
    os.makedirs(outdir, exist_ok=True)
    for ag in airgaps:
        sensor_z = ag/1000.0
        thetas = np.linspace(0,2*math.pi,theta_steps,endpoint=False)
        bx = np.zeros_like(thetas)
        by = np.zeros_like(thetas)
        for idx, th in enumerate(thetas):
            rotated_centers = []
            for m in mags:
                c = np.array(m['center'])
                cr = np.array([c[0]*math.cos(th)-c[1]*math.sin(th), c[0]*math.sin(th)+c[1]*math.cos(th), c[2]])
                mm = dict(m)
                mm['center'] = cr
                rotated_centers.append(mm)
            sensor_pos = np.array([sensor_r/1000.0, 0.0, sensor_z])
            B = compute_field_from_magnets(rotated_centers, sensor_pos, model=model, Br=Br, discrete_grid=discrete_grid)
            bx[idx] = B[0]; by[idx] = B[1]
        complex_signal = np.ascontiguousarray(np.array(bx, dtype=np.float64) + 1j * np.array(by, dtype=np.float64), dtype=np.complex128)
        fft = np.fft.fft(complex_signal)
        amps = np.abs(fft)/len(complex_signal)
        fundamental = amps[1] if len(amps)>1 else 0.0
        thd = 100.0 * np.sqrt(np.sum(amps[2:]**2)) / (fundamental + 1e-30)
        results.append({'airgap_mm': float(ag), 'amp_fund': float(fundamental), 'thd_pct': float(thd)})
        plt.figure(figsize=(8,4))
        plt.plot(np.degrees(thetas), bx, label='Bx')
        plt.plot(np.degrees(thetas), by, label='By')
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
    cfg = yaml.safe_load(open(args.config))
    run_sim(cfg)

if __name__ == '__main__':
    main()
