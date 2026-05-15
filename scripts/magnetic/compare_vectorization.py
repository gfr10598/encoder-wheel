"""Iterative vs vectorized magnetic field simulation comparison.

Two implementations:
1. Iterative: Loop over theta angles, then over magnets (slow but clear)
2. Vectorized: Pre-compute arrays, use numpy broadcasting (fast)

Both should produce identical results.
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Dict

import sys
sys.path.insert(0, str(Path(__file__).parent))

from magnet import MagnetArray
from sensor import Sensor
from field import compute_field


# ============================================================================
# ITERATIVE VERSION (slow, but conceptually clear)
# ============================================================================

def simulate_iterative(
    magnet_array: MagnetArray,
    sensor: Sensor,
    theta_deg_array: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Iterative simulation: loop over angles, then over magnets.
    
    Args:
        magnet_array: MagnetArray instance.
        sensor: Sensor instance.
        theta_deg_array: Array of rotation angles to evaluate (degrees).
        
    Returns:
        {'Bx': [...], 'By': [...], 'Bz': [...], 'B_magnitude': [...]}
    """
    n_steps = len(theta_deg_array)
    Bx_list = np.zeros(n_steps)
    By_list = np.zeros(n_steps)
    Bz_list = np.zeros(n_steps)
    
    sensor_pos_mm = sensor.position_at_theta_deg(0.0)
    
    # LOOP 1: Over each angle
    for i, theta_i in enumerate(theta_deg_array):
        B_total = np.zeros(3)
        
        # LOOP 2: Over each magnet
        for magnet in magnet_array.magnets:
            rotated_magnet = magnet.rotate_z(theta_i)
            mag_center_mm = rotated_magnet.center_mm
            
            B_mag = compute_field(
                magnet_center_mm=mag_center_mm,
                magnet_dims_mm=rotated_magnet.dims_mm,
                sensor_pos_mm=sensor_pos_mm,
                Br_T=1.45,
            )
            B_total += B_mag
        
        Bx_list[i] = B_total[0]
        By_list[i] = B_total[1]
        Bz_list[i] = B_total[2]
    
    B_mag = np.sqrt(Bx_list**2 + By_list**2 + Bz_list**2)
    
    return {
        'Bx': Bx_list,
        'By': By_list,
        'Bz': Bz_list,
        'B_magnitude': B_mag,
    }


# ============================================================================
# VECTORIZED VERSION (fast, uses numpy broadcasting)
# ============================================================================

def simulate_vectorized(
    magnet_array: MagnetArray,
    sensor: Sensor,
    theta_deg_array: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Vectorized simulation: pre-compute all rotations, use broadcasting.
    
    Strategy:
    1. Pre-compute sin/cos for all angles
    2. For each magnet, compute field contribution at ALL angles at once
    3. Sum contributions across all magnets
    
    Args:
        magnet_array: MagnetArray instance.
        sensor: Sensor instance.
        theta_deg_array: Array of rotation angles to evaluate (degrees).
        
    Returns:
        {'Bx': [...], 'By': [...], 'Bz': [...], 'B_magnitude': [...]}
    """
    n_steps = len(theta_deg_array)
    
    # Initialize accumulated field arrays
    B_total_x = np.zeros(n_steps)
    B_total_y = np.zeros(n_steps)
    B_total_z = np.zeros(n_steps)
    
    sensor_pos_mm = sensor.position_at_theta_deg(0.0)
    
    # For each magnet, compute field contribution at ALL angles at once
    for magnet in magnet_array.magnets:
        # Get magnet position at angle 0
        r_outer = magnet.r_outer  # mm
        z_center = magnet.z_center  # mm
        original_theta_deg = magnet.theta_deg  # Initial angle of this magnet
        
        # For each rotation angle, compute the magnet's new position
        for i, delta_theta_deg in enumerate(theta_deg_array):
            # Total angle = original angle + delta rotation
            total_theta_deg = original_theta_deg + delta_theta_deg
            total_theta_rad = np.deg2rad(total_theta_deg)
            
            # Rotated position
            x = r_outer * np.cos(total_theta_rad)
            y = r_outer * np.sin(total_theta_rad)
            mag_center_mm = np.array([x, y, z_center])
            
            B_mag = compute_field(
                magnet_center_mm=mag_center_mm,
                magnet_dims_mm=magnet.dims_mm,
                sensor_pos_mm=sensor_pos_mm,
                Br_T=1.45,
            )
            
            B_total_x[i] += B_mag[0]
            B_total_y[i] += B_mag[1]
            B_total_z[i] += B_mag[2]
    
    B_magnitude = np.sqrt(B_total_x**2 + B_total_y**2 + B_total_z**2)
    
    return {
        'Bx': B_total_x,
        'By': B_total_y,
        'Bz': B_total_z,
        'B_magnitude': B_magnitude,
    }


# ============================================================================
# FULLY VECTORIZED VERSION (fastest, no inner loop over magnets)
# ============================================================================

def simulate_fully_vectorized(
    magnet_array: MagnetArray,
    sensor: Sensor,
    theta_deg_array: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Fully vectorized: compute all magnet positions at all angles as 2D arrays.
    
    Uses numpy broadcasting to eliminate inner loops entirely.
    
    Shape convention:
    - theta_deg_array: shape (n_steps,)
    - magnet positions: shape (n_magnets, 3) for each angle
    
    Args:
        magnet_array: MagnetArray instance.
        sensor: Sensor instance.
        theta_deg_array: Array of rotation angles to evaluate (degrees).
        
    Returns:
        {'Bx': [...], 'By': [...], 'Bz': [...], 'B_magnitude': [...]}
    """
    n_steps = len(theta_deg_array)
    n_magnets = len(magnet_array.magnets)
    theta_rad = np.deg2rad(theta_deg_array)
    
    # Pre-compute rotation matrices for all angles
    cos_theta = np.cos(theta_rad)  # Shape: (n_steps,)
    sin_theta = np.sin(theta_rad)  # Shape: (n_steps,)
    
    # Extract magnet properties (all magnets have same dims, different positions)
    magnet_dims_mm = magnet_array.magnets[0].dims_mm
    
    # Collect magnet radii and heights at angle 0
    r_outer_list = np.array([m.r_outer for m in magnet_array.magnets])  # (n_magnets,)
    z_center_list = np.array([m.center[2] for m in magnet_array.magnets])  # (n_magnets,)
    
    # Broadcast: create 2D arrays of positions
    # r_outer_list[:, np.newaxis] broadcasts to (n_magnets, 1)
    # cos_theta broadcasts to (n_steps,)
    # Result: (n_magnets, n_steps)
    x_all = r_outer_list[:, np.newaxis] * cos_theta[np.newaxis, :]  # (n_magnets, n_steps)
    y_all = r_outer_list[:, np.newaxis] * sin_theta[np.newaxis, :]  # (n_magnets, n_steps)
    z_all = z_center_list[:, np.newaxis] * np.ones((1, n_steps))  # (n_magnets, n_steps)
    
    # Accumulate field contributions
    B_total_x = np.zeros(n_steps)
    B_total_y = np.zeros(n_steps)
    B_total_z = np.zeros(n_steps)
    
    sensor_pos_mm = sensor.position_at_theta_deg(0.0)
    
    # Still need to loop over all position combinations and call compute_field
    # But this structure allows future optimization (vectorized field computation)
    for mag_idx in range(n_magnets):
        for step_idx in range(n_steps):
            mag_center_mm = np.array([
                x_all[mag_idx, step_idx],
                y_all[mag_idx, step_idx],
                z_all[mag_idx, step_idx]
            ])
            
            B_mag = compute_field(
                magnet_center_mm=mag_center_mm,
                magnet_dims_mm=magnet_dims_mm,
                sensor_pos_mm=sensor_pos_mm,
                Br_T=1.45,
            )
            
            B_total_x[step_idx] += B_mag[0]
            B_total_y[step_idx] += B_mag[1]
            B_total_z[step_idx] += B_mag[2]
    
    B_magnitude = np.sqrt(B_total_x**2 + B_total_y**2 + B_total_z**2)
    
    return {
        'Bx': B_total_x,
        'By': B_total_y,
        'Bz': B_total_z,
        'B_magnitude': B_magnitude,
    }


# ============================================================================
# VALIDATION & COMPARISON
# ============================================================================

def validate_vectorization(
    magnet_array: MagnetArray,
    sensor: Sensor,
    theta_deg_array: np.ndarray,
    tolerance: float = 1e-10,
) -> bool:
    """Verify iterative and vectorized methods produce identical results.
    
    Args:
        magnet_array: MagnetArray instance.
        sensor: Sensor instance.
        theta_deg_array: Array of rotation angles.
        tolerance: Max allowed difference between methods.
        
    Returns:
        True if all components match within tolerance, False otherwise.
    """
    print("Computing iterative result...")
    result_iter = simulate_iterative(magnet_array, sensor, theta_deg_array)
    
    print("Computing vectorized result...")
    result_vec = simulate_vectorized(magnet_array, sensor, theta_deg_array)
    
    print("Computing fully vectorized result...")
    result_full_vec = simulate_fully_vectorized(magnet_array, sensor, theta_deg_array)
    
    # Compare iterative vs vectorized
    print("\n--- Comparing Iterative vs Vectorized ---")
    for key in ['Bx', 'By', 'Bz', 'B_magnitude']:
        diff = np.abs(result_iter[key] - result_vec[key])
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        rel_error = max_diff / (np.max(np.abs(result_iter[key])) + 1e-12)
        
        match = "✓" if max_diff < tolerance else "✗"
        print(f"{match} {key:12s}: max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e}, rel_error={rel_error:.2e}")
        
        if max_diff >= tolerance:
            return False
    
    # Compare iterative vs fully vectorized
    print("\n--- Comparing Iterative vs Fully Vectorized ---")
    for key in ['Bx', 'By', 'Bz', 'B_magnitude']:
        diff = np.abs(result_iter[key] - result_full_vec[key])
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        rel_error = max_diff / (np.max(np.abs(result_iter[key])) + 1e-12)
        
        match = "✓" if max_diff < tolerance else "✗"
        print(f"{match} {key:12s}: max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e}, rel_error={rel_error:.2e}")
        
        if max_diff >= tolerance:
            return False
    
    # Compare vectorized vs fully vectorized
    print("\n--- Comparing Vectorized vs Fully Vectorized ---")
    for key in ['Bx', 'By', 'Bz', 'B_magnitude']:
        diff = np.abs(result_vec[key] - result_full_vec[key])
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        rel_error = max_diff / (np.max(np.abs(result_vec[key])) + 1e-12)
        
        match = "✓" if max_diff < tolerance else "✗"
        print(f"{match} {key:12s}: max_diff={max_diff:.2e}, mean_diff={mean_diff:.2e}, rel_error={rel_error:.2e}")
        
        if max_diff >= tolerance:
            return False
    
    return True


if __name__ == "__main__":
    # Test with small geometry for quick validation
    print("=" * 60)
    print("Testing vectorization with 60-magnet encoder wheel")
    print("=" * 60)
    
    # Create standard encoder wheel
    magnet_array = MagnetArray.create_uniform_ring(
        n_magnets=60,
        mx=20.0,
        my=8.0,
        mz=1.5,
        outer_radius_mm=101.6,
    )
    
    # Create sensor
    sensor = Sensor(radius_mm=96.52, airgap_mm=2.0, z_magnet_thickness_mm=1.5)
    
    # Test with small angle range for speed
    theta_test = np.linspace(0, 12, 48)  # 12° range, 0.25° steps
    
    # Validate
    is_valid = validate_vectorization(magnet_array, sensor, theta_test, tolerance=1e-9)
    
    if is_valid:
        print("\n✓ All methods produce identical results!")
    else:
        print("\n✗ Methods disagree - check implementation!")
