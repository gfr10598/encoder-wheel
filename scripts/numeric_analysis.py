#!/usr/bin/env python3
"""Numeric vs dipole single-magnet analysis.
Writes JSON results for multiple grid resolutions and airgaps.
"""
import os, sys, math, json, argparse
import numpy as np
import yaml
sys.path.insert(0, os.path.dirname(__file__))
from analysis_utils import compute_field_from_magnets, magnet_dipole_from_block, dipole_field
from coords import cyl_to_cart


def build_single_magnet(cfg):
    outer = cfg['outer_radius_mm']
    magnet_dims = cfg['magnet_dims_mm']
    Br = cfg.get('Br_T', 1.45)
    r_center = outer - magnet_dims[0] + magnet_dims[0]/2.0
    # place magnet at theta=0 (x positive)
    theta = 0.0
    x = r_center*math.cos(theta)
    y = r_center*math.sin(theta)
    # single magnet: poles through faces (axis along z)
    axis_vec = (0.0, 0.0, 1.0)
    # place magnet with its large face against the disk top at z=0
    mz = magnet_dims[2] / 2.0
    # place magnet center so lower face sits at z=0 (upper face at T)
    mag = {'center':[x,y,mz], 'dims':magnet_dims, 'axis':axis_vec, 'Br':Br}
    return mag


def run(cfg, airgaps_mm, grids, outpath):
    mag = build_single_magnet(cfg)
    sensor_offset_from_outer = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    outer = cfg['outer_radius_mm']
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
    results = []
    for ag in airgaps_mm:
        sensor_z = (mag['dims'][2] + ag)/1000.0
        sensor_theta_deg = float(cfg.get('sensor_theta_deg', 0.0))
        sensor_pos = cyl_to_cart(sensor_r/1000.0, math.radians(sensor_theta_deg), sensor_z)
        entry = {'airgap_mm': float(ag), 'sensor_pos_m': sensor_pos.tolist(), 'methods':{}}
        # dipole single-dipole
        m_vec = magnet_dipole_from_block(mag['Br'], mag['dims'], mag['axis'])
        center_m = np.array(mag['center'])/1000.0
        B_dip = dipole_field(m_vec, sensor_pos - center_m)
        entry['methods']['dipole'] = {'B_T': B_dip.tolist(), 'B_mT': (B_dip*1e3).tolist(), 'm_vec': m_vec.tolist()}
        # numeric for each grid
        for g in grids:
            Bnum = compute_field_from_magnets([mag], sensor_pos, model='discrete', Br=mag['Br'], discrete_grid=tuple(g), steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
            key = f'discrete_{g[0]}x{g[1]}x{g[2]}'
            entry['methods'][key] = {'B_T': Bnum.tolist(), 'B_mT': (Bnum*1e3).tolist()}
            # compute simple vector differences to dipole
            diff = Bnum - B_dip
            entry['methods'][key]['diff_T'] = diff.tolist()
            entry['methods'][key]['rel_err_pct'] = (np.linalg.norm(diff) / (np.linalg.norm(B_dip)+1e-30))*100.0
        results.append(entry)
    with open(outpath,'w') as f:
        json.dump(results,f,indent=2)
    # print compact summary
    for r in results:
        ag = r['airgap_mm']
        dip = np.array(r['methods']['dipole']['B_mT'])
        print(f"airgap {ag} mm: dipole |B|={np.linalg.norm(dip):.3f} mT")
        for k,v in r['methods'].items():
            if k == 'dipole':
                continue
            b = np.array(v['B_mT'])
            print(f"  {k}: |B|={np.linalg.norm(b):.3f} mT, rel_err={v['rel_err_pct']:.2f}%")
    return outpath

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    p.add_argument('--airgaps', nargs='+', type=float, default=[3.0,4.0])
    p.add_argument('--out', default='examples/plots/numeric_single_magnet.json')
    p.add_argument('--grids', nargs='*', default=['4,4,2','8,8,4','12,12,6'])
    args = p.parse_args()
    cfg = yaml.safe_load(open(args.config))
    grids = [tuple(map(int,g.split(','))) for g in args.grids]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    run(cfg, args.airgaps, grids, args.out)
