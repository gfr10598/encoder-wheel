#!/usr/bin/env python3
import os, sys, math, json, argparse
import numpy as np
# Set matplotlib backend BEFORE importing pyplot to avoid multiprocessing issues
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
from analysis_utils import compute_field_from_magnets
from coords import cyl_to_cart
from common_config import load_config, validate_config

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

def compute_field_analytic_vectorized(mags, sensor_pos, n, theta_steps, thetas, Br=1.45):
    """Compute field using analytic rectangular prism method, vectorized over theta points."""
    from analysis_utils import analytic_rect_prism_B
    
    cos_th = np.cos(thetas)
    sin_th = np.sin(thetas)
    
    bx = np.zeros(theta_steps)
    by = np.zeros(theta_steps)
    bz = np.zeros(theta_steps)
    
    for mi in range(n):
        m = mags[mi]
        cx, cy, cz = m['center']
        
        # Rotate center for all theta values
        cx_rot = cx * cos_th - cy * sin_th
        cy_rot = cx * sin_th + cy * cos_th
        cz_rot = np.full(theta_steps, cz)
        
        # Compute analytic field for each rotated position
        for idx in range(theta_steps):
            center_rot_mm = [cx_rot[idx], cy_rot[idx], cz_rot[idx]]
            try:
                B = analytic_rect_prism_B(center_rot_mm, m['dims'], m['axis'], sensor_pos, Br=Br)
                bx[idx] += B[0]
                by[idx] += B[1]
                bz[idx] += B[2]
            except Exception as e:
                # Skip magnets with issues (e.g., non-z-axis magnetization)
                pass
    
    return bx, by, bz

def compute_airgap_result(params):
    """Compute field analysis for a single airgap using both discrete and analytic methods. Vectorized over all theta points."""
    ag, mags, sensor_pos, n, theta_steps, theta_end_rad, model, Br, discrete_grid, steel_params, outdir = params
    thetas = np.linspace(0, theta_end_rad, theta_steps, endpoint=False)
    
    # Compute all methods for comparison
    # Method 1a: Discrete coarse (10×4×1)
    bx_disc_coarse, by_disc_coarse, bz_disc_coarse = compute_field_discrete_vectorized(mags, sensor_pos, n, theta_steps, thetas, Br, (10, 4, 1))
    
    # Method 1b: Discrete fine (20×8×3)
    bx_disc_fine, by_disc_fine, bz_disc_fine = compute_field_discrete_vectorized(mags, sensor_pos, n, theta_steps, thetas, Br, (20, 8, 3))
    
    # Method 2: Analytic (rectangular prism closed-form)
    bx_ana, by_ana, bz_ana = compute_field_analytic_vectorized(mags, sensor_pos, n, theta_steps, thetas, Br)
    
    # Use discrete coarse for main metrics (backward compatibility)
    bx_disc = bx_disc_coarse
    by_disc = by_disc_coarse
    bz_disc = bz_disc_coarse
    
    # Use discrete method for main metrics
    bx = bx_disc
    by = by_disc
    bz = bz_disc
    
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
    
    # Compute energy (sum of squared values) for both methods
    energy_by_disc = float(np.sum(by_disc**2))
    energy_bz_disc = float(np.sum(bz_disc**2))
    energy_by_ana = float(np.sum(by_ana**2))
    energy_bz_ana = float(np.sum(bz_ana**2))
    
    # Energy ratios
    by_bz_ratio_disc = energy_by_disc / energy_bz_disc if energy_bz_disc > 0 else 0
    by_bz_ratio_ana = energy_by_ana / energy_bz_ana if energy_bz_ana > 0 else 0
    
    # Plot both methods side-by-side: discrete vs analytic for By (tangential) and Bz (axial)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    
    # By (tangential/encoder signal)
    axes[0].plot(np.degrees(thetas), by_disc*1e3, label='Discrete', linewidth=2, color='C0')
    axes[0].plot(np.degrees(thetas), by_ana*1e3, label='Analytic', linewidth=1.5, linestyle='--', alpha=0.7, color='C1')
    
    # Mark expected peaks (at 3° and 9° for alternating polarity)
    axes[0].axvline(3, color='gray', linestyle=':', alpha=0.5, label='Expected peaks')
    axes[0].axvline(9, color='gray', linestyle=':', alpha=0.5)
    axes[0].axvline(0, color='red', linestyle='-.', alpha=0.3, linewidth=0.8, label='Expected zeros')
    axes[0].axvline(6, color='red', linestyle='-.', alpha=0.3, linewidth=0.8)
    axes[0].axvline(12, color='red', linestyle='-.', alpha=0.3, linewidth=0.8)
    
    axes[0].set_ylabel('By (tangential) [mT]')
    axes[0].legend(loc='upper left')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title(f'Encoder signal: By (airgap {ag} mm)')
    
    # Bz (axial/pole field)
    axes[1].plot(np.degrees(thetas), bz_disc*1e3, label='Discrete', linewidth=2, color='C0')
    axes[1].plot(np.degrees(thetas), bz_ana*1e3, label='Analytic', linewidth=1.5, linestyle='--', alpha=0.7, color='C1')
    axes[1].set_xlabel('disk rotation (deg)')
    axes[1].set_ylabel('Bz (axial) [mT]')
    axes[1].legend(loc='upper left')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_title(f'Pole field: Bz (airgap {ag} mm)')
    
    # Add energy ratios as text box (By/Bz, not discrete/analytic)
    energy_text = f'Energy Ratio (By/Bz):\n'
    energy_text += f'Discrete: {by_bz_ratio_disc:.3f}\n'
    energy_text += f'Analytic: {by_bz_ratio_ana:.3f}\n'
    energy_text += f'\n'
    energy_text += f'Absolute Energy:\n'
    energy_text += f'By_disc:  {energy_by_disc:.4e}\n'
    energy_text += f'Bz_disc:  {energy_bz_disc:.4e}\n'
    energy_text += f'By_ana:   {energy_by_ana:.4e}\n'
    energy_text += f'Bz_ana:   {energy_bz_ana:.4e}'
    
    fig.text(0.98, 0.97, energy_text, transform=fig.transFigure, 
             fontsize=9, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8), family='monospace')
    
    plt.tight_layout(rect=[0, 0, 0.75, 1])  # Leave room for text box
    plt.savefig(os.path.join(outdir, f'compare_methods_{int(ag*100)}.png'), dpi=100)
    plt.close()
    
    return result

def compute_field_discrete_vectorized(mags, sensor_pos, n, theta_steps, thetas, Br, discrete_grid):
    """Compute field using discrete (volumetric) method, vectorized over theta points.
    Uses shared vector_utils for all dipole field calculations."""
    from analysis_utils import discretize_block, magnet_dipole_from_block
    from vector_utils import compute_dipole_field, compute_voxel_moment
    
    cos_th = np.cos(thetas)
    sin_th = np.sin(thetas)
    
    bx = np.zeros(theta_steps)
    by = np.zeros(theta_steps)
    bz = np.zeros(theta_steps)
    
    # Vectorized field computation: rotate all magnets for all theta points at once
    for mi in range(n):
        m = mags[mi]
        cx, cy, cz = m['center']
        
        # Rotate center for all theta values at once (broadcasting)
        cx_rot = cx * cos_th - cy * sin_th
        cy_rot = cx * sin_th + cy * cos_th
        cz_rot = np.full(theta_steps, cz)
        
        # Compute field contribution from this magnet at all theta points
        if discrete_grid != (1, 1, 1):
            dg = tuple(discrete_grid) if len(discrete_grid) == 3 else (discrete_grid[0], discrete_grid[1], 1)
            subs = discretize_block(m['center'], m['dims'], m['axis'], grid=dg)
            
            # Pre-compute total moment and per-voxel moment
            m_total_vec = magnet_dipole_from_block(Br, m['dims'], m['axis'])
            nsubs = dg[0] * dg[1] * dg[2]
            ax_unit = np.array(m['axis'], dtype=float)
            ax_norm = np.linalg.norm(ax_unit)
            if ax_norm > 0:
                ax_unit = ax_unit / ax_norm
            m_voxel = compute_voxel_moment(m_total_vec, nsubs, ax_unit)
            
            # For each sub-dipole, compute field at all theta points in batch
            for sub_center_m, axis_unit in subs:
                # sub_center_m is in meters; compute offset from magnet center in mm
                sub_x_mm = sub_center_m[0] * 1000 - m['center'][0]
                sub_y_mm = sub_center_m[1] * 1000 - m['center'][1]
                sub_z_mm = sub_center_m[2] * 1000 - m['center'][2]
                
                # Rotate sub-dipole position around magnet center
                sub_x_rot = sub_x_mm * cos_th - sub_y_mm * sin_th
                sub_y_rot = sub_x_mm * sin_th + sub_y_mm * cos_th
                sub_z_rot = sub_z_mm
                
                # Add rotated magnet center (convert to meters)
                sub_x_final = (cx_rot + sub_x_rot) / 1000.0
                sub_y_final = (cy_rot + sub_y_rot) / 1000.0
                sub_z_final = (cz_rot + sub_z_rot) / 1000.0
                
                # Stack all positions for vectorized field computation
                point_positions = np.stack([sub_x_final, sub_y_final, sub_z_final], axis=1)  # (N, 3)
                
                # Use shared compute_dipole_field with broadcasting: (3,) moment, (3,) sensor, (N,3) points
                # Returns (N, 3) field contributions
                B_contrib = compute_dipole_field(m_voxel, sensor_pos, point_positions)
                bx += B_contrib[:, 0]
                by += B_contrib[:, 1]
                bz += B_contrib[:, 2]
        else:
            # Simple dipole model
            m_vec = magnet_dipole_from_block(Br, m['dims'], m['axis'])
            
            # Stack all positions for vectorized field computation
            point_positions = np.stack([cx_rot/1000.0, cy_rot/1000.0, cz_rot/1000.0], axis=1)  # (N, 3)
            
            # Use shared compute_dipole_field with broadcasting
            B_contrib = compute_dipole_field(m_vec, sensor_pos, point_positions)
            bx += B_contrib[:, 0]
            by += B_contrib[:, 1]
            bz += B_contrib[:, 2]
    
    return bx, by, bz

def run_sim(cfg, single_airgap_mm=None):
    """Run simulation for all airgaps (or single airgap if specified)."""
    n = cfg['n_magnets']
    outer = cfg['outer_radius_mm']
    sensor_offset_from_outer = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
    magnet_dims = cfg['magnet_dims_mm']
    Br = cfg.get('Br_T', 1.45)
    
    # Determine which airgaps to compute
    if single_airgap_mm is not None:
        airgaps = np.array([float(single_airgap_mm)])
    else:
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
    
    # Run airgaps sequentially (vectorized per-airgap)
    results = []
    for item in work_items:
        result = compute_airgap_result(item)
        results.append(result)
    
    # Sort results by airgap for consistent output
    results.sort(key=lambda r: r['airgap_mm'])
    
    summary_path = cfg.get('summary_path', os.path.join(outdir,'summary.json'))
    with open(summary_path,'w') as f:
        json.dump(results,f,indent=2)
    print('Done. Summary written to', summary_path)

def main():
    p = argparse.ArgumentParser(description='Analyze magnetic field for encoder wheel across airgap range')
    p.add_argument('--config', required=True, help='Config YAML file')
    p.add_argument('--airgap', type=float, default=None, help='Compute single airgap (mm) only (for parallel batch processing)')
    args = p.parse_args()
    cfg = load_config(args.config)
    validate_config(cfg, ['n_magnets', 'outer_radius_mm', 'magnet_dims_mm'])
    run_sim(cfg, single_airgap_mm=args.airgap)

if __name__ == '__main__':
    main()
