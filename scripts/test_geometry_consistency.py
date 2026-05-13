#!/usr/bin/env python3
"""Test if dipole, numeric, and analytic methods receive identical geometry."""
import sys, os, math, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from analysis_utils import compute_field_from_magnets, analytic_rect_prism_B, dipole_field, magnet_dipole_from_block, discretize_block
from coords import cyl_to_cart

# Single magnet test: place one magnet centered on X-axis, sensor on Y-axis
magnet_dims = [20.0, 8.0, 1.5]  # [L, W, T] in mm
Br = 1.45  # Tesla
mag_center_mm = [50.0, 0.0, 0.75]  # magnet center in mm (T/2 above z=0)
mag_axis = (0.0, 0.0, 1.0)  # magnetized along +Z

# Sensor at (0, 48, 6.5) mm = 0.048 m radially, 6.5 mm above magnet top
sensor_pos_m = np.array([0.0, 48.0/1000.0, 6.5/1000.0])

print("=" * 70)
print("SINGLE MAGNET GEOMETRY TEST")
print("=" * 70)
print(f"Magnet center (mm): {mag_center_mm}")
print(f"Magnet dims (mm): {magnet_dims}")
print(f"Magnet axis: {mag_axis}")
print(f"Br (T): {Br}")
print(f"Sensor pos (m): {sensor_pos_m}")
print()

# METHOD 1: Dipole (direct)
print("METHOD 1: DIPOLE (via compute_field_from_magnets)")
magnet_list = [{'center': mag_center_mm, 'dims': magnet_dims, 'axis': mag_axis, 'Br': Br}]
B_dipole = compute_field_from_magnets(magnet_list, sensor_pos_m, model='dipole', Br=Br)
print(f"  B = {B_dipole} T = {B_dipole*1e3} mT")
print()

# METHOD 2: Numeric (8x8x4)
print("METHOD 2: NUMERIC (8x8x4 grid via compute_field_from_magnets)")
B_numeric = compute_field_from_magnets(magnet_list, sensor_pos_m, model='discrete', Br=Br, discrete_grid=(8,8,4))
print(f"  B = {B_numeric} T = {B_numeric*1e3} mT")
print(f"  Diff from dipole: {(B_numeric - B_dipole)*1e3} mT ({100*np.linalg.norm(B_numeric-B_dipole)/np.linalg.norm(B_dipole):.1f}%)")
print()

# METHOD 3: Analytic (direct call)
print("METHOD 3: ANALYTIC (direct analytic_rect_prism_B call)")
B_analytic = analytic_rect_prism_B(mag_center_mm, magnet_dims, mag_axis, sensor_pos_m, Br=Br)
print(f"  B = {B_analytic} T = {B_analytic*1e3} mT")
print(f"  Diff from dipole: {(B_analytic - B_dipole)*1e3} mT ({100*np.linalg.norm(B_analytic-B_dipole)/np.linalg.norm(B_dipole):.1f}%)")
print()

# METHOD 4: Manual dipole check
print("METHOD 4: MANUAL DIPOLE (direct dipole_field call)")
m_vec = magnet_dipole_from_block(Br, magnet_dims, mag_axis)
print(f"  Magnetic moment: {m_vec} A·m²")
r_vec = sensor_pos_m - np.array([c/1000.0 for c in mag_center_mm])
print(f"  Sensor rel. to magnet: {r_vec} m = {r_vec*1000} mm")
B_manual = dipole_field(m_vec, r_vec)
print(f"  B = {B_manual} T = {B_manual*1e3} mT")
print()

# METHOD 5: Numeric manual via discretize_block
print("METHOD 5: NUMERIC MANUAL (discretize 8x8x4 + sum dipoles)")
sub_dipoles = discretize_block(mag_center_mm, magnet_dims, mag_axis, (8, 8, 4))
B_numeric_manual = np.array([0.0, 0.0, 0.0])
for sub_center, sub_moment in sub_dipoles:
    r_sub = sensor_pos_m - np.array([c/1000.0 for c in sub_center])
    B_numeric_manual += dipole_field(sub_moment, r_sub)
print(f"  B = {B_numeric_manual} T = {B_numeric_manual*1e3} mT")
print(f"  Diff from numeric method: {(B_numeric_manual - B_numeric)*1e3} mT ({100*np.linalg.norm(B_numeric_manual-B_numeric)/np.linalg.norm(B_numeric):.1f}%)")
print()

print("=" * 70)
print("SUMMARY")
print("=" * 70)
methods = {
    'Dipole (via compute)': B_dipole,
    'Numeric (8x8x4)': B_numeric,
    'Analytic': B_analytic,
    'Dipole (manual)': B_manual,
    'Numeric (manual)': B_numeric_manual
}
for name, B in methods.items():
    print(f"{name:30s} {B*1e3:9.3f} mT  |B|={np.linalg.norm(B)*1e3:.3f} mT")
