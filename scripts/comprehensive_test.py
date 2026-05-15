#!/usr/bin/env python3
"""
Comprehensive fresh-start test suite.
"""

import numpy as np


def analytic_rect_prism(center_mm, dims_mm, sensor_mm, Br_T=1.45):
    """Analytic field from uniformly magnetized rectangular prism."""
    center = np.array(center_mm, dtype=float) / 1000.0
    sensor = np.array(sensor_mm, dtype=float) / 1000.0
    dims = np.array(dims_mm, dtype=float) / 1000.0
    
    rel_pos = sensor - center
    dx, dy, dz = rel_pos
    
    L, W, T = dims
    a, b, c = L/2.0, W/2.0, T/2.0
    
    X = np.array([dx - a, dx + a])
    Y = np.array([dy - b, dy + b])
    Z = np.array([dz - c, dz + c])
    
    M = Br_T
    
    Bz_sum = 0.0
    Bx_sum = 0.0
    By_sum = 0.0
    
    for i in range(2):
        for j in range(2):
            for k in range(2):
                x = X[i]
                y = Y[j]
                z = Z[k]
                
                r = np.sqrt(x**2 + y**2 + z**2)
                if r < 1e-12:
                    continue
                
                sgn = (-1.0)**(i + j + k)
                
                Bz_sum += sgn * np.arctan2(x*y, z*r)
                Bx_sum += sgn * np.log(max(y + r, 1e-12))
                By_sum += sgn * np.log(max(x + r, 1e-12))
    
    scale = M / (4*np.pi)
    
    Bz = scale * Bz_sum
    Bx = -scale * Bx_sum
    By = -scale * By_sum
    
    return np.array([Bx, By, Bz])


def discrete_dipole(center_mm, dims_mm, sensor_mm, Br_T=1.45, grid=(20, 8, 2)):
    """Discrete voxel dipole method."""
    center = np.array(center_mm, dtype=float) / 1000.0
    sensor = np.array(sensor_mm, dtype=float) / 1000.0
    dims = np.array(dims_mm, dtype=float) / 1000.0
    
    L, W, T = dims
    a, b, c = L/2.0, W/2.0, T/2.0
    
    nx, ny, nz = grid
    dx = L / nx
    dy = W / ny
    dz = T / nz
    
    dV = dx * dy * dz
    
    mu0 = 4*np.pi*1e-7
    M = Br_T / mu0
    m_voxel = M * dV
    
    xs = np.linspace(-a + dx/2, a - dx/2, nx)
    ys = np.linspace(-b + dy/2, b - dy/2, ny)
    zs = np.linspace(-c + dz/2, c - dz/2, nz)
    
    B = np.zeros(3)
    
    for x_v in xs:
        for y_v in ys:
            for z_v in zs:
                voxel_pos = center + np.array([x_v, y_v, z_v])
                r_vec = sensor - voxel_pos
                r = np.linalg.norm(r_vec)
                
                if r > 1e-6:
                    m_vec = np.array([0., 0., m_voxel])
                    m_dot_r = np.dot(m_vec, r_vec)
                    B += (mu0/(4*np.pi)) * (3*m_dot_r*r_vec/r**5 - m_vec/r**3)
    
    return B


print("=" * 120)
print("COMPREHENSIVE TEST SUITE: Fresh Start Implementation")
print("=" * 120)

dims = [20.0, 8.0, 1.5]  # Encoder wheel magnet size
test_cases = [
    ("Centered magnet", [0.0, 0.0, 0.0], [15.0, 5.0, 4.5]),
    ("Offset radially", [50.0, 0.0, 0.75], [65.0, 5.0, 5.25]),
    ("Encoder wheel (0°)", [91.6, 0.0, 0.75], [106.6, 4.0, 5.25]),
    ("Encoder wheel (45°)", [64.8, 64.8, 0.75], [78.0, 78.0, 5.25]),
    ("Encoder wheel (90°)", [0.0, 91.6, 0.75], [4.0, 106.6, 5.25]),
    ("Close to magnet", [0.0, 0.0, 0.0], [5.0, 2.0, 2.0]),
    ("Far from magnet", [0.0, 0.0, 0.0], [50.0, 30.0, 30.0]),
]

all_passed = True

for name, center, sensor in test_cases:
    B_ana = analytic_rect_prism(center, dims, sensor)
    B_disc = discrete_dipole(center, dims, sensor)
    
    mag_ana = np.linalg.norm(B_ana)
    mag_disc = np.linalg.norm(B_disc)
    
    if mag_ana > 1e-12:
        error_pct = 100 * abs(mag_disc - mag_ana) / mag_ana
    else:
        error_pct = 0.0
    
    passed = error_pct < 1.0  # Accept <1% error
    all_passed = all_passed and passed
    
    status = "✓ PASS" if passed else "✗ FAIL"
    
    print(f"\n{status} | {name:30s} | Error: {error_pct:8.4f}%")
    print(f"     Analytic: {mag_ana*1000:10.6f} mT  |  Discrete: {mag_disc*1000:10.6f} mT")

print("\n" + "=" * 120)
if all_passed:
    print("SUCCESS: All tests passed! Fresh implementation is correct.")
    print("\nNext steps: Integrate this into the main codebase and verify full simulation.")
else:
    print("FAILURE: Some tests failed. Need further debugging.")
print("=" * 120)
