import math
import numpy as np
from vector_utils import (
    mu0, br_to_m, sensor_to_point_vector, compute_dipole_field,
    compute_dipole_moment_from_block, compute_voxel_moment, validate_magnetic_moment
)

# Legacy interface for backward compatibility
def dipole_field(m_vec, r_vec):
    """Legacy wrapper for compute_dipole_field via vector_utils.
    
    Computes B field at sensor from dipole moment m_vec at distance r_vec.
    Supports both scalar vectors (3,) and array broadcasting (N, 3).
    
    Args:
        m_vec: dipole moment vector (T·m³) - shape (3,) or (N, 3)
        r_vec: displacement from dipole to sensor (m) - shape (3,) or (N, 3)
    
    Returns:
        B field (T) - same shape as m_vec / r_vec
    """
    # compute_dipole_field expects (sensor_pos, dipole_pos) and computes sensor - dipole.
    # Since r_vec is already "sensor - dipole", we pass it as sensor_pos with dipole at origin.
    return compute_dipole_field(m_vec, r_vec, np.array([0., 0., 0.]))

def magnet_dipole_from_block(Br, dims, axis):
    """Legacy wrapper for compute_dipole_moment_from_block."""
    return compute_dipole_moment_from_block(Br, dims, axis)

def discretize_block(center, dims, axis, grid=(1,1,1)):
    """Discretize block into sub-dipoles.

    center: [x,y,z] in mm
    dims: [L,W,T] in mm (L=radial length, W=tangential width, T=thickness)
    grid: (nx,ny,nz) number of subdivisions along each axis
    returns list of (pos_m, axis_unit)
    
    IMPORTANT: Voxel offsets are created in MAGNET-LOCAL COORDINATES:
    - L-axis points radially outward from disk center
    - W-axis points tangentially (perpendicular to radius)
    - T-axis points along Z (disk normal)
    
    These offsets are then rotated to align with the magnet's actual angle
    based on its center position in the ring.
    """
    from magnet_transform import get_magnet_angle, transform_to_global
    
    L, W, T = dims
    nx, ny, nz = grid
    sub = []
    
    # Create offsets in magnet-local coordinates
    xs = np.linspace(-L/2, L/2, nx+1)[:-1] + (L/nx)/2  # Radial offsets
    ys = np.linspace(-W/2, W/2, ny+1)[:-1] + (W/ny)/2  # Tangential offsets
    zs = np.linspace(-T/2, T/2, nz+1)[:-1] + (T/nz)/2  # Z offsets
    
    # Compute magnet's angle from its center position
    theta = get_magnet_angle(center)
    
    # Normalize axis vector
    axis_arr = np.array(axis, dtype=float)
    norm = np.linalg.norm(axis_arr)
    if norm == 0:
        axis_unit = axis_arr
    else:
        axis_unit = axis_arr / norm
    
    for xi in xs:  # Radial offset
        for yi in ys:  # Tangential offset
            for zi in zs:  # Z offset
                # Local offset point (in mm)
                offset_local_mm = np.array([xi, yi, zi])
                # Transform to global coordinates (in mm)
                offset_global_mm = transform_to_global(offset_local_mm, theta)
                # Add to magnet center and convert to meters
                pos = (np.array(center) + offset_global_mm) / 1000.0
                sub.append((pos, axis_unit))
    return sub

def compute_field_from_magnets(mag_list, sensor_pos, model='dipole', Br=1.45, discrete_grid=(1,1,1), steel_mu_r=None, steel_image_factor=None, steel_backing_thickness_mm=None, steel_plane_z=None):
    """Compute B at sensor_pos from mag_list.

    `discrete_grid` may be a 2-tuple (nx,ny) or 3-tuple (nx,ny,nz). Normalize
    to 3-tuple internally so callers using 2-tuple don't accidentally trigger
    the discrete branch when they intended dipole behavior.
    """
    # normalize discrete_grid to 3-tuple
    dg = tuple(discrete_grid)
    if len(dg) == 2:
        dg = (dg[0], dg[1], 1)
    elif len(dg) == 1:
        dg = (dg[0], 1, 1)
    B = np.zeros(3)
    # determine image factor and plane if requested
    image_factor = None
    if steel_image_factor is not None:
        image_factor = float(steel_image_factor)
    elif steel_mu_r is not None:
        mu_r = float(steel_mu_r)
        image_factor = (mu_r - 1.0) / (mu_r + 1.0)

    plane_z = None
    if steel_plane_z is not None:
        plane_z = float(steel_plane_z)
    elif steel_backing_thickness_mm is not None:
        # assume backing upper face (top) is at z = 0.0 (magnets sit on disk)
        plane_z = 0.0

    for mag in mag_list:
        center = np.array(mag['center'])/1000.0
        dims = mag['dims']
        axis = mag['axis']
        local_Br = mag.get('Br', Br)
        # treat as dipole only when requested and grid is 1x1x1
        if model == 'dipole' and dg == (1,1,1):
            m = magnet_dipole_from_block(local_Br, dims, axis)
            r = sensor_pos - center
            B += dipole_field(m, r)
            # add image dipole if configured
            if image_factor is not None and plane_z is not None:
                center_img = center.copy()
                center_img[2] = 2*plane_z - center[2]
                m_img = m * image_factor
                B += dipole_field(m_img, sensor_pos - center_img)
        else:
            grid = dg
            subs = discretize_block(mag['center'], dims, axis, grid=grid)
            m_total_vec = magnet_dipole_from_block(local_Br, dims, axis)
            nsubs = grid[0] * grid[1] * grid[2]
            if nsubs <= 0:
                continue
            # Use vector_utils to compute per-voxel moment
            ax_unit = np.array(axis, dtype=float)
            ax_norm = np.linalg.norm(ax_unit)
            if ax_norm > 0:
                ax_unit = ax_unit / ax_norm
            m_voxel = compute_voxel_moment(m_total_vec, nsubs, ax_unit)
            
            for pos, ax in subs:
                r = sensor_pos - pos
                # Each sub-dipole has moment m_voxel, already in correct direction
                B += dipole_field(m_voxel, r)
                # mirrored sub-dipole for steel backing
                if image_factor is not None and plane_z is not None:
                    pos_img = pos.copy()
                    pos_img[2] = 2*plane_z - pos[2]
                    m_img = m_voxel * image_factor
                    B += dipole_field(m_img, sensor_pos - pos_img)
    return B


def analytic_rect_prism_B(center_mm, dims_mm, axis, sensor_pos, Br=1.45, eps=1e-9, use_gemini=False):
    """Compute B (T) at `sensor_pos` (meters) from a uniformly magnetized
    rectangular prism (external field) using closed-form corner-sum expressions.
    
    **NOTE**: The gemini implementation has inverted sign convention and should 
    NOT be used (available for debugging). The original algebraic implementation 
    (use_gemini=False, default) matches numeric results perfectly.

    center_mm: [x,y,z] in mm (prism center)
    dims_mm: [L, W, T] full extents in mm (edges 2a,2b,2c)
             where L points radially, W points tangentially
    axis: magnetization axis tuple (only z supported)
    sensor_pos: numpy array (m)
    Br: remanent flux density (T)
    eps: small number to stabilize logs/atan2
    use_gemini: if True (NOT RECOMMENDED), use gemini implementation (opposite sign)
    """
    from magnet_transform import get_magnet_angle, transform_to_magnet_local, transform_vector_to_global
    
    import numpy as _np
    # only support axis roughly along z
    axis_arr = _np.array(axis, dtype=float)
    axis_norm = _np.linalg.norm(axis_arr)
    if axis_norm == 0:
        raise ValueError('zero axis')
    ax_unit = axis_arr / axis_norm
    if abs(abs(ax_unit[2]) - 1.0) > 1e-6:
        raise NotImplementedError('analytic_rect_prism_B supports z-axis magnetization only')

    # convert dims/center to meters and local coordinates
    cx, cy, cz = (_np.array(center_mm, dtype=float) / 1000.0).tolist()
    L, W, T = dims_mm
    a = (L/2.0) / 1000.0
    b = (W/2.0) / 1000.0
    c = (T/2.0) / 1000.0

    # Compute magnet's angle and transform sensor position into magnet-local frame
    theta = get_magnet_angle(center_mm)
    
    # Sensor position relative to magnet center in global coords
    sensor_rel_global = _np.array([sensor_pos[0] - cx, sensor_pos[1] - cy, sensor_pos[2] - cz])
    
    # Transform into magnet-local frame using transformation module
    sensor_rel_local = transform_to_magnet_local(sensor_rel_global, theta)
    x = sensor_rel_local[0]
    y = sensor_rel_local[1]
    z = sensor_rel_local[2]

    # If requested, delegate to the gemini implementation for compatibility.
    if use_gemini:
        try:
            from importlib import import_module
            gp = import_module('scripts.gemini-field-formula')
        except Exception:
            # fallback to run_path if import fails
            import runpy
            gp = runpy.run_path('scripts/gemini-field-formula.py')
        compute_magnetic_field_mm = gp.get('compute_magnetic_field_mm') if isinstance(gp, dict) else getattr(gp, 'compute_magnetic_field_mm', None)
        if compute_magnetic_field_mm is None:
            raise RuntimeError('gemini implementation not found')
        # gemini expects position in mm relative to magnet center and half-dims
        pos_mm = [(sensor_pos[0] - cx) * 1000.0, (sensor_pos[1] - cy) * 1000.0, (sensor_pos[2] - cz) * 1000.0]
        half_dims = [d/2.0 for d in dims_mm]
        Bg = compute_magnetic_field_mm(pos_mm, half_dims, Br)
        return np.array(Bg)

    M = br_to_m(Br)

    def f(u, v, w):
        r = _np.sqrt(u*u + v*v + w*w)
        # stabilize
        rp = r + eps
        term1 = u * _np.log((v + rp) + eps)
        term2 = v * _np.log((u + rp) + eps)
        # use atan2 for robust quadrant handling
        term3 = - w * _np.arctan2(u * v, w * rp + eps)
        return term1 + term2 + term3

    # potential phi from top and bottom faces difference (magnetized along +z)
    # φ = (M / (4π)) * Σ_{s1=±1} Σ_{s2=±1} s1*s2 * [ f(x - s1*a, y - s2*b, z - c) - f(x - s1*a, y - s2*b, z + c) ]
    svals = [-1.0, 1.0]
    total = 0.0
    for sx in svals:
        for sy in svals:
            sign = sx * sy
            u = x - sx * a
            v = y - sy * b
            total += sign * (f(u, v, z - c) - f(u, v, z + c))

    phi = (M / (4.0 * math.pi)) * total

    # compute analytic partial derivatives of f and assemble grad(phi)
    def df_du(u, v, w):
        r = _np.sqrt(u*u + v*v + w*w)
        rp = r + eps
        denom = (u*u) * (v*v) + (w*w) * (r*r) + eps
        # terms from differentiation
        term_ln = _np.log(v + rp + eps)
        term1 = term_ln + (u*u) / (r * (v + rp + eps))
        term2 = v / r
        term3 = 0.0
        # robust atan-related derivative term
        if denom > 0:
            term3 = - (w*w) * v * (v*v + w*w) / (r * denom)
        return term1 + term2 + term3

    def df_dv(u, v, w):
        # symmetric in u/v
        r = _np.sqrt(u*u + v*v + w*w)
        rp = r + eps
        denom = (u*u) * (v*v) + (w*w) * (r*r) + eps
        term_ln = _np.log(u + rp + eps)
        term1 = term_ln + (v*v) / (r * (u + rp + eps))
        term2 = u / r
        term3 = 0.0
        if denom > 0:
            term3 = - (w*w) * u * (u*u + w*w) / (r * denom)
        return term1 + term2 + term3

    def df_dw(u, v, w):
        r = _np.sqrt(u*u + v*v + w*w)
        rp = r + eps
        denom = (u*u) * (v*v) + (w*w) * (r*r) + eps
        term1 = (u * w) / (r * (v + rp + eps))
        term2 = (v * w) / (r * (u + rp + eps))
        atan_term = _np.arctan2(u * v, w * r + eps)
        term3 = 0.0
        if denom > 0:
            term3 = (w * u * v * (r + (w*w)/r)) / denom
        return term1 + term2 - atan_term + term3

    # assemble gradient components by summing corner contributions
    gx = 0.0
    gy = 0.0
    gz = 0.0
    for sx in svals:
        for sy in svals:
            sign = sx * sy
            u = x - sx * a
            v = y - sy * b
            # for z-c term
            w1 = z - c
            # for z+c term
            w2 = z + c
            gx += sign * (df_du(u, v, w1) - df_du(u, v, w2))
            gy += sign * (df_dv(u, v, w1) - df_dv(u, v, w2))
            gz += sign * (df_dw(u, v, w1) - df_dw(u, v, w2))

    coeff = (M / (4.0 * math.pi))
    grad_phi_x = coeff * gx
    grad_phi_y = coeff * gy
    grad_phi_z = coeff * gz

    grad = _np.array([grad_phi_x, grad_phi_y, grad_phi_z])
    H = -grad
    B_local = mu0 * H
    # if magnetization is -z, flip sign
    if ax_unit[2] < 0:
        B_local = -B_local
    
    # Transform field components back from magnet-local to global coordinates
    B_global = transform_vector_to_global(B_local, theta)
    
    return B_global
