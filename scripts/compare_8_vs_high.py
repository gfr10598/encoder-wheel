#!/usr/bin/env python3
import json, numpy as np, math
from scripts.analysis_utils import compute_field_from_magnets, analytic_rect_prism_B
from scripts.common_config import load_config, validate_config
from scripts.coords import cyl_to_cart

cfg = load_config("examples/configs/encoder_wheel_config.md")
validate_config(cfg, ['outer_radius_mm', 'magnet_dims_mm'])
outer = cfg['outer_radius_mm']
mag_dims = cfg['magnet_dims_mm']
Br = cfg.get('Br_T', 1.45)
mag_center = [outer - mag_dims[0]/2.0, 0.0, mag_dims[2]/2.0]
mag = {'center':mag_center,'dims':mag_dims,'axis':(0,0,1),'Br':Br}

sensor_r = cfg.get('sensor_radius_mm', outer - 5.0)
airgap = 5.0
# sensor z measured from magnet top face (magnet top = magnet thickness)
sensor_z = (mag_dims[2] + airgap)/1000.0
# For this single-point comparison use theta = 1.5 degrees
sensor_theta_deg = 1.5
sensor_pos = cyl_to_cart(sensor_r/1000.0, math.radians(sensor_theta_deg), sensor_z)

B_8 = compute_field_from_magnets([mag], sensor_pos, model='discrete', Br=Br, discrete_grid=(8,8,4), steel_mu_r=cfg.get('steel_mu_r'), steel_image_factor=cfg.get('steel_image_factor'), steel_backing_thickness_mm=cfg.get('steel_backing_thickness_mm'), steel_plane_z=cfg.get('steel_plane_z'))
B_analytic = analytic_rect_prism_B(mag_center, mag_dims, mag['axis'], sensor_pos, Br=Br)
B_high = np.array(json.load(open('examples/plots/numeric_single_magnet_highres_48x48x24.json'))['B_numeric_48x48x24_T'])

def stats(name, B):
    B = np.array(B)
    norm = np.linalg.norm(B)
    return f"{name}: B(T)={B.tolist()}, |B|={norm:.6f} T = {norm*1e3:.3f} mT"

print(stats('8x8x4 numeric', B_8))
print(stats('analytic', B_analytic))
print(stats('48x48x24 numeric', B_high))

def relpct(A,B):
    return np.linalg.norm(A-B)/ (np.linalg.norm(B)+1e-30) * 100.0

print('\nRelative differences (pct):')
print(f"8x8x4 vs analytic: {relpct(B_8, B_analytic):.2f}%")
print(f"48x48x24 vs analytic: {relpct(B_high, B_analytic):.2f}%")
print(f"8x8x4 vs 48x48x24: {relpct(B_8, B_high):.2f}%")

comp_8_anal = (B_8 - B_analytic)*1e3
comp_hr_anal = (B_high - B_analytic)*1e3
print('\nComponent diffs (mT) relative to analytic:')
print('8x8x4 - analytic (mT)=', comp_8_anal.tolist())
print('48x48x24 - analytic (mT)=', comp_hr_anal.tolist())
