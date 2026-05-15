#!/usr/bin/env python3
"""
Fixed analytic and discrete field calculations.
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
    
    M = Br_T  # Magnetization (Tesla)
    
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
    
    # Magnetization: M = Br/mu0
    mu0 = 4*np.pi*1e-7
    M = Br_T / mu0  # A/m
    m_voxel = M * dV  # magnetic moment per voxel (A·m²)
    
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


# Test
print("Testing discrete vs analytic...")

center = [0.0, 0.0, 0.0]
dims = [20.0, 8.0, 1.5]
sensor = [15.0, 5.0, 4.5]

B_ana = analytic_rect_prism(center, dims, sensor)
B_disc = discrete_dipole(center, dims, sensor)

print(f"\nAnalytic: {B_ana*1000} mT")
print(f"Discrete: {B_disc*1000} mT")
print(f"\nAnalytic magnitude: {np.linalg.norm(B_ana)*1000:.6f} mT")
print(f"Discrete magnitude: {np.linalg.norm(B_disc)*1000:.6f} mT")

error = 100*abs(np.linalg.norm(B_disc) - np.linalg.norm(B_ana))/np.linalg.norm(B_ana)
print(f"Error: {error:.4f}%")
