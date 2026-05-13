import math
import numpy as np
mu0 = 4.0 * math.pi * 1e-7

def br_to_m(Br):
    return Br / mu0

def dipole_field(m_vec, r_vec):
    r = np.linalg.norm(r_vec)
    if r == 0:
        return np.zeros(3)
    m = np.array(m_vec)
    rhat = r_vec / r
    return (mu0 / (4 * math.pi)) * (3 * rhat * np.dot(m, rhat) - m) / (r ** 3)

def magnet_dipole_from_block(Br, dims, axis):
    L, W, T = dims
    V = (L/1000.0) * (W/1000.0) * (T/1000.0)
    M = br_to_m(Br)
    m_mag = M * V
    return np.array(axis) * m_mag

def discretize_block(center, dims, axis, grid=(1,1)):
    L, W, T = dims
    nx, ny = grid
    sub = []
    xs = np.linspace(-L/2, L/2, nx+1)[:-1] + (L/nx)/2
    ys = np.linspace(-W/2, W/2, ny+1)[:-1] + (W/ny)/2
    for xi in xs:
        for yi in ys:
            pos = np.array([center[0] + xi, center[1] + yi, center[2]])/1000.0
            sub.append((pos, np.array(axis)))
    return sub

def compute_field_from_magnets(mag_list, sensor_pos, model='dipole', Br=1.45, discrete_grid=(1,1)):
    B = np.zeros(3)
    for mag in mag_list:
        center = np.array(mag['center'])/1000.0
        dims = mag['dims']
        axis = mag['axis']
        local_Br = mag.get('Br', Br)
        if model == 'dipole' and discrete_grid==(1,1):
            m = magnet_dipole_from_block(local_Br, dims, axis)
            r = sensor_pos - center
            B += dipole_field(m, r)
        else:
            grid = discrete_grid
            subs = discretize_block(mag['center'], dims, axis, grid=grid)
            m_total = magnet_dipole_from_block(local_Br, dims, axis)
            m_per = m_total / (grid[0]*grid[1])
            for pos, ax in subs:
                r = sensor_pos - pos
                B += dipole_field(m_per * ax, r)
    return B
