#!/usr/bin/env python3
import runpy, yaml, json, numpy as np, os
from scripts.analysis_utils import compute_field_from_magnets, analytic_rect_prism_B

def main():
    cfg = yaml.safe_load(open('examples/configs/n52_20x8x1.5_60_outer4in_sensor3p8in_fine.yaml'))
    outer = cfg['outer_radius_mm']; mag_dims = cfg['magnet_dims_mm']; Br = cfg.get('Br_T',1.45)
    mag_center = [outer - mag_dims[0]/2.0, 0.0, mag_dims[2]/2.0]
    mag = {'center':mag_center,'dims':mag_dims,'axis':(0,0,1),'Br':Br}
    sensor_offset_from_outer = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
    airgap = 5.0
    y_off_mm = 2.5
    # sensor z measured from magnet top face: magnet top = magnet_thickness
    sensor_pos = np.array([sensor_r/1000.0, y_off_mm/1000.0, (mag_dims[2] + airgap)/1000.0])
    gp = runpy.run_path('scripts/gemini-field-formula.py')
    compute_magnetic_field_mm = gp['compute_magnetic_field_mm']
    pos_mm = (sensor_pos - np.array(mag_center)/1000.0) * 1000.0
    half_dims = [d/2.0 for d in mag_dims]
    B_gem = compute_magnetic_field_mm(pos_mm.tolist(), half_dims, Br)
    B_analytic = analytic_rect_prism_B(mag_center, mag_dims, mag['axis'], sensor_pos, Br=Br)
    B_8 = compute_field_from_magnets([mag], sensor_pos, model='discrete', Br=Br, discrete_grid=(8,8,4), steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
    B_48 = compute_field_from_magnets([mag], sensor_pos, model='discrete', Br=Br, discrete_grid=(48,48,24), steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
    out = {'sensor_pos_m': sensor_pos.tolist(), 'pos_mm_rel_to_mag_center': pos_mm.tolist(), 'analytic_T': B_analytic.tolist(), 'gemini_T': [float(x) for x in B_gem], 'numeric_8x8x4_T': B_8.tolist(), 'numeric_48x48x24_T': B_48.tolist(), 'Br_T': Br}
    os.makedirs('examples/plots', exist_ok=True)
    outpath = 'examples/plots/offsym_2.5mm_compare_5mm.json'
    with open(outpath, 'w') as f:
        json.dump(out, f, indent=2)
    print('Wrote', outpath)
    print('sensor_pos_m:', sensor_pos)
    print('analytic (T):', B_analytic)
    print('gemini (T):', B_gem)
    print('numeric 8x8x4 (T):', B_8)
    print('numeric 48x48x24 (T):', B_48)

if __name__ == '__main__':
    main()
