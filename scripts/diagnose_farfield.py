#!/usr/bin/env python3
"""Diagnose far-field vs near-field discrepancies between dipole and numeric."""
import sys, os, math, yaml, numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
from analysis_utils import compute_field_from_magnets
from coords import cyl_to_cart

# Load config
cfg = yaml.safe_load(open('examples/configs/n52_20x8x1.5_60_outer4in_sensor3p8in_fine.yaml'))
n, outer, dims = cfg['n_magnets'], cfg['outer_radius_mm'], cfg['magnet_dims_mm']
r_inner = outer - dims[0]
r_center = r_inner + dims[0]/2.0
Br = cfg['Br_T']
sensor_r_mm = cfg['sensor_radius_mm']
sensor_theta_deg = cfg.get('sensor_theta_deg', 0.0)
airgap_mm = 4.0
sensor_z_m = (dims[2] + airgap_mm) / 1000.0

# Build ring magnets
def build_ring_config(n_magnets, r_inner, magnet_dims, Br=1.45):
    r_center = r_inner + magnet_dims[0]/2.0
    mags = []
    for i in range(n_magnets):
        theta = 2*math.pi*i/n_magnets
        x = r_center*math.cos(theta)
        y = r_center*math.sin(theta)
        polarity = -1.0 if (i % 2) else 1.0
        axis_vec = (0.0, 0.0, polarity)
        mz = magnet_dims[2] / 2.0
        mags.append({'center': [x,y,0.0], 'dims': magnet_dims, 'axis': axis_vec, 'Br': Br})
    return mags

mags = build_ring_config(n, r_inner, dims, Br=Br)
# Adjust z
for m in mags:
    m['center'][2] = dims[2] / 2.0

# Test at key theta angles
test_thetas_deg = [0, 5, 10, 20, 36, 72]  # 0=nearest magnet, 36=half-ring, 72=far side
theta_steps = 2048
thetas_rad = np.linspace(0, 2*math.pi, theta_steps, endpoint=False)

print("=" * 80)
print("FAR-FIELD DISCREPANCY ANALYSIS")
print("=" * 80)
print(f"Config: {n} magnets, airgap={airgap_mm}mm, sensor_r={sensor_r_mm}mm")
print(f"Magnet center radius: {r_center:.1f} mm")
print()

for test_theta_deg in test_thetas_deg:
    test_theta_rad = math.radians(test_theta_deg)
    
    # Rotate magnets by this angle (what compare_methods does)
    rotated = []
    for m in mags:
        c = np.array(m['center'])
        cr = np.array([c[0]*math.cos(test_theta_rad) - c[1]*math.sin(test_theta_rad),
                       c[0]*math.sin(test_theta_rad) + c[1]*math.cos(test_theta_rad),
                       c[2]])
        a = np.array(m['axis'])
        ar = np.array([a[0]*math.cos(test_theta_rad) - a[1]*math.sin(test_theta_rad),
                       a[0]*math.sin(test_theta_rad) + a[1]*math.cos(test_theta_rad),
                       a[2]])
        mm = dict(m)
        mm['center'] = cr
        mm['axis'] = (float(ar[0]), float(ar[1]), float(ar[2]))
        rotated.append(mm)
    
    # Sensor position
    sensor_pos = cyl_to_cart(sensor_r_mm/1000.0, math.radians(sensor_theta_deg), sensor_z_m)
    
    # Compute fields
    B_dip = compute_field_from_magnets(rotated, sensor_pos, model='dipole', Br=Br)
    B_num = compute_field_from_magnets(rotated, sensor_pos, model='discrete', Br=Br, discrete_grid=(8,8,4))
    
    # Analyze nearby magnets
    sensor_m = sensor_pos
    dists_to_magnets = []
    for i, m in enumerate(rotated):
        m_m = np.array([c/1000.0 for c in m['center']])
        dist = np.linalg.norm(sensor_m - m_m) * 1000
        dists_to_magnets.append((dist, i))
    
    dists_to_magnets.sort()
    closest_3 = dists_to_magnets[:3]
    
    print(f"θ = {test_theta_deg:3d}° : Bx_dip={B_dip[0]*1e3:7.2f} mT, Bx_num={B_num[0]*1e3:7.2f} mT, By_dip={B_dip[1]*1e3:7.2f} mT, By_num={B_num[1]*1e3:7.2f} mT")
    print(f"         Closest magnets: #{closest_3[0][1]} @ {closest_3[0][0]:.1f}mm, #{closest_3[1][1]} @ {closest_3[1][0]:.1f}mm, #{closest_3[2][1]} @ {closest_3[2][0]:.1f}mm")
    print()
