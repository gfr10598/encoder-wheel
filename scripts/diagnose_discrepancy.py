#!/usr/bin/env python3
import runpy, numpy as np, json, os
from scripts.analysis_utils import compute_field_from_magnets, analytic_rect_prism_B, magnet_dipole_from_block, discretize_block
from scripts.common_config import load_config, validate_config

cfg = load_config('examples/configs/n52_20x8x1.5_60_outer4in_sensor3p8in_fine.yaml')
validate_config(cfg, ['outer_radius_mm', 'magnet_dims_mm'])
outer = cfg['outer_radius_mm']
mag_dims = cfg['magnet_dims_mm']
Br = cfg.get('Br_T',1.45)
mag_center = [outer - mag_dims[0]/2.0, 0.0, mag_dims[2]/2.0]
mag = {'center':mag_center, 'dims':mag_dims, 'axis':(0,0,1), 'Br':Br}

# gemini loader
gp = runpy.run_path('scripts/gemini-field-formula.py')
compute_magnetic_field_mm = gp.get('compute_magnetic_field_mm')

airgaps = [3.0,4.0]
grids = [(8,8,4),(16,16,8),(24,24,12),(48,48,24)]
results = {}
for ag in airgaps:
    res_ag = {}
    sensor_offset_from_outer = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
    # sensor z measured from magnet top face: magnet top = magnet_thickness
    sensor_pos_base = np.array([sensor_r/1000.0,0.0,(mag_dims[2] + ag)/1000.0])
    # compute methods with and without steel
    for steel_mode in ['with_steel','no_steel']:
        use_steel = steel_mode=='with_steel'
        res_mode = {}
        # dipole
        Bdip = compute_field_from_magnets([mag], sensor_pos_base, model='dipole', Br=Br, discrete_grid=(1,1,1), steel_mu_r=(cfg.get('steel_mu_r') if use_steel else None), steel_image_factor=(cfg.get('steel_image_factor') if use_steel else None), steel_backing_thickness_mm=(cfg.get('steel_backing_thickness_mm') if use_steel else None), steel_plane_z=(cfg.get('steel_plane_z') if use_steel else None))
        Barr = analytic_rect_prism_B(mag['center'], mag['dims'], mag['axis'], sensor_pos_base, Br=Br)
        # gemini
        pos_mm = (sensor_pos_base - np.array(mag_center)/1000.0) * 1000.0
        Bgem = compute_magnetic_field_mm(pos_mm.tolist(), [d/2.0 for d in mag_dims], Br)
        res_mode['dipole_T'] = Bdip.tolist(); res_mode['analytic_T'] = Barr.tolist(); res_mode['gemini_T'] = [float(x) for x in Bgem]
        # numeric grids
        res_mode['numeric'] = {}
        for g in grids:
            Bnum = compute_field_from_magnets([mag], sensor_pos_base, model='discrete', Br=Br, discrete_grid=g, steel_mu_r=(cfg.get('steel_mu_r') if use_steel else None), steel_image_factor=(cfg.get('steel_image_factor') if use_steel else None), steel_backing_thickness_mm=(cfg.get('steel_backing_thickness_mm') if use_steel else None), steel_plane_z=(cfg.get('steel_plane_z') if use_steel else None))
            res_mode['numeric'][f'{g[0]}x{g[1]}x{g[2]}'] = {'B_T': Bnum.tolist(), 'norm_mT': float(np.linalg.norm(Bnum)*1e3)}
        res_ag[steel_mode] = res_mode
    results[f'{int(ag)}mm'] = res_ag

# check discrete dipole sum conservation
m_total = magnet_dipole_from_block(Br, mag_dims, mag['axis'])
subs = discretize_block(mag['center'], mag_dims, mag['axis'], grid=(48,48,24))
# compute per-sub dipole magnitude used by compute_field_from_magnets
nsubs = 48*48*24
m_per = np.linalg.norm(m_total)/nsubs
mvecs = [m_per * np.array(ax)/np.linalg.norm(ax) for pos,ax in subs]
sum_vec = np.sum(mvecs, axis=0)
results['dipole_moments'] = {'m_total': m_total.tolist(), 'sum_sub_m_vec': sum_vec.tolist(), 'nsubs': nsubs}

os.makedirs('examples/plots', exist_ok=True)
with open('examples/plots/diagnostics_3_4mm.json','w') as f:
    json.dump(results, f, indent=2)

# simple convergence plot
import matplotlib.pyplot as plt
for ag in airgaps:
    gs = [g[0] for g in grids]
    nums = [results[f'{int(ag)}mm']['with_steel']['numeric'][f'{g}x{g}x{int(g/2)}']['norm_mT'] for g in gs]
    nums_no = [results[f'{int(ag)}mm']['no_steel']['numeric'][f'{g}x{g}x{int(g/2)}']['norm_mT'] for g in gs]
    an = np.linalg.norm(np.array(results[f'{int(ag)}mm']['no_steel']['analytic_T']))*1e3
    gm = np.linalg.norm(np.array(results[f'{int(ag)}mm']['no_steel']['gemini_T']))*1e3
    plt.figure()
    plt.plot(gs, nums, 'o-', label='numeric w/ steel')
    plt.plot(gs, nums_no, 's--', label='numeric no steel')
    plt.axhline(an, color='C3', linestyle='--', label=f'analytic no steel |B|={an:.1f} mT')
    plt.axhline(gm, color='C4', linestyle='-.', label=f'gemini no steel |B|={gm:.1f} mT')
    plt.xlabel('grid N'); plt.ylabel('|B| (mT)'); plt.title(f'Convergence at {int(ag)} mm')
    plt.legend(); plt.grid(True)
    plt.savefig(f'examples/plots/diagnostics_convergence_{int(ag)}mm.png', bbox_inches='tight')

print('Wrote examples/plots/diagnostics_3_4mm.json and convergence PNGs')
