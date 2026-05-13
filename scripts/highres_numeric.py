#!/usr/bin/env python3
import runpy, numpy as np, json, os
from scripts.analysis_utils import compute_field_from_magnets
from scripts.common_config import load_config, validate_config


def main():
    cfg = load_config("examples/configs/n52_20x8x1.5_60_outer4in_sensor3p8in_fine.yaml")
    validate_config(cfg, ['outer_radius_mm', 'magnet_dims_mm'])
    outer = cfg['outer_radius_mm']; mag_dims = cfg['magnet_dims_mm']; Br = cfg.get('Br_T', 1.45)
    mag_center=[outer - mag_dims[0]/2.0, 0.0, mag_dims[2]/2.0]
    mag={'center':mag_center,'dims':mag_dims,'axis':(0,0,1),'Br':Br}
    sensor_offset_from_outer = float(cfg.get('sensor_offset_from_outer_mm', 5.0))
    sensor_r = float(cfg.get('sensor_radius_mm', outer - sensor_offset_from_outer))
    airgap=5.0
    # sensor z measured from magnet top face: magnet top = magnet_thickness
    sensor_pos = np.array([sensor_r/1000.0,0.0,(mag_dims[2] + airgap)/1000.0])
    print('Computing numeric with grid 48x48x24...')
    Bnum_high = compute_field_from_magnets([mag], sensor_pos, model='discrete', Br=Br, discrete_grid=(48,48,24), steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
    print('B_numeric high-res (T):', Bnum_high)
    out={'B_numeric_48x48x24_T': Bnum_high.tolist()}
    os.makedirs('examples/plots', exist_ok=True)
    with open('examples/plots/numeric_single_magnet_highres_48x48x24.json','w') as f:
        json.dump(out,f,indent=2)
    print('Wrote examples/plots/numeric_single_magnet_highres_48x48x24.json')

if __name__ == '__main__':
    main()
