#!/usr/bin/env python3
import os, sys, math, json, argparse
import numpy as np
# Set matplotlib backend BEFORE importing pyplot to avoid multiprocessing issues
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor
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

def compute_airgap_result(params):
    """Compute field analysis for a single airgap. Called in parallel worker."""
    ag, mags, sensor_pos, n, theta_steps, theta_end_rad, model, Br, discrete_grid, steel_params, outdir = params
    bx = np.zeros(theta_steps)
    by = np.zeros(theta_steps)
    bz = np.zeros(theta_steps)
    thetas = np.linspace(0, theta_end_rad, theta_steps, endpoint=False)
    
    for idx, th in enumerate(thetas):
        rotated_centers = []
        for mi in range(n):
            m = mags[mi]
            c = np.array(m['center'])
            cr = np.array([c[0]*math.cos(th)-c[1]*math.sin(th), c[0]*math.sin(th)+c[1]*math.cos(th), c[2]])
            mm = dict(m)
            mm['center'] = cr
            # Magnetization axis stays fixed in lab frame (Z direction); don't rotate it
            rotated_centers.append(mm)
        
        B = compute_field_from_magnets(rotated_centers, sensor_pos, model=model, Br=Br, 
                                       discrete_grid=discrete_grid, **steel_params)
        bx[idx] = B[0]; by[idx] = B[1]; bz[idx] = B[2]
    
    # FFT analysis
    complex_signal = np.ascontiguousarray(np.array(bx, dtype=np.float64) + 1j * np.array(by, dtype=np.float64), dtype=np.complex128)
    N = len(complex_signal)
    fft_c = np.fft.fft(complex_signal)
    amps_c = np.abs(fft_c)/N
    fft_bx = np.fft.fft(bx)
    amps_bx = np.abs(fft_bx)/N
    fft_by = np.fft.fft(by)
    amps_by = np.abs(fft_by)/N
    
    fund_idx = max(1, n//2)
    fundamental_c = amps_c[fund_idx] if len(amps_c)>fund_idx else 0.0
    fundamental_bx = amps_bx[fund_idx] if len(amps_bx)>fund_idx else 0.0
    fundamental_by = amps_by[fund_idx] if len(amps_by)>fund_idx else 0.0
    thd = 100.0 * np.sqrt(np.sum(amps_c[fund_idx+1:]**2)) / (fundamental_c + 1e-30)
    
    # Symmetry checks
    checks = {}
    checks['mean_bx'] = float(np.mean(bx))
    checks['mean_by'] = float(np.mean(by))
    checks['mean_bz'] = float(np.mean(bz))
    max_bx = float(np.max(bx))
    min_bx = float(np.min(bx))
    checks['peak_symmetry_bx'] = abs(max_bx - abs(min_bx)) / (max(abs(max_bx), abs(min_bx)) + 1e-30)
    sample_idxs = (np.linspace(0, N, n, endpoint=False)).astype(int)
    bz_at_mags = bz[sample_idxs]
    inv_diffs = []
    for i in range(len(bz_at_mags)//2):
        a = bz_at_mags[2*i]
        b = bz_at_mags[(2*i+1) % len(bz_at_mags)]
        inv_diffs.append(abs(a + b) / (max(abs(a), abs(b)) + 1e-30))
    checks['perp_inv_mean_rel'] = float(np.mean(inv_diffs)) if inv_diffs else 0.0
    
    result = {'airgap_mm': float(ag), 'amp_fund_mT': float(fundamental_c*1e3), 
              'amp_fund_bx_mT': float(fundamental_bx*1e3), 'amp_fund_by_mT': float(fundamental_by*1e3), 
              'thd_pct': float(thd), 'checks': checks}
    
    # Plot tangential (By) and axial (Bz) components
    plt.figure(figsize=(8,4))
    plt.plot(np.degrees(thetas), by*1e3, label='By (tangential)')
    plt.plot(np.degrees(thetas), bz*1e3, label='Bz (axial)')
    plt.xlabel('disk rotation (deg)'); plt.legend(); plt.title(f'airgap {ag} mm')
    plt.tight_layout()
    plt.savefig(os.path.join(outdir,f'raw_B_{int(ag*100)}.png'))
    plt.close()
    
    return result

def run_sim(cfg):
    n = cfg['n_magnets']
    outer = cfg['outer_radius_mm']
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
    
    outdir = cfg.get('outdir','examples/plots')
    os.makedirs(outdir, exist_ok=True)
    
    # Prepare parameters for all airgaps
    # Sensor fixed at theta=0 in lab frame; disk rotates beneath it
    sensor_theta_deg = 0.0
    theta_sweep_deg = float(cfg.get('theta_sweep_deg', 360.0))
    theta_end_rad = math.radians(theta_sweep_deg)
    steel_params = {
        'steel_mu_r': cfg.get('steel_mu_r'),
        'steel_image_factor': cfg.get('steel_image_factor'),
        'steel_backing_thickness_mm': cfg.get('steel_backing_thickness_mm'),
        'steel_plane_z': cfg.get('steel_plane_z')
    }
    # Remove None values
    steel_params = {k: v for k, v in steel_params.items() if v is not None}
    
    work_items = []
    for ag in airgaps:
        sensor_z = (magnet_dims[2] + ag)/1000.0
        sensor_pos = cyl_to_cart(sensor_r/1000.0, math.radians(sensor_theta_deg), sensor_z)
        work_items.append((ag, mags, sensor_pos, n, theta_steps, theta_end_rad, model, Br, discrete_grid, steel_params, outdir))
    
    # Run 8 airgaps in parallel
    results = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        for result in executor.map(compute_airgap_result, work_items):
            results.append(result)
    
    # Sort results by airgap for consistent output
    results.sort(key=lambda r: r['airgap_mm'])
    
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
