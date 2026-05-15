"""Main simulation engine for encoder wheel magnetic field.

Computes full 360° magnetic field response as magnet disk rotates.
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Dict

# Add scripts to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from magnet import MagnetArray
from sensor import Sensor
from field import compute_field


def simulate_full_rotation(
    magnet_array: MagnetArray,
    sensor: Sensor,
    theta_start_deg: float = 0.0,
    theta_end_deg: float = 360.0,
    n_steps: int = 1920,
) -> Dict[str, np.ndarray]:
    """Simulate field response over full magnet rotation.
    
    Args:
        magnet_array: MagnetArray instance with positioned magnets.
        sensor: Sensor instance defining measurement point.
        theta_start_deg: Starting rotation angle (default: 0°).
        theta_end_deg: Ending rotation angle (default: 360°).
        n_steps: Number of angular steps to evaluate (default: 1920 for 0.1875° resolution).
        
    Returns:
        Dictionary with keys:
            - 'theta_deg': Array of rotation angles (degrees)
            - 'theta_rad': Array of rotation angles (radians)
            - 'Bx': Array of radial field components (Tesla)
            - 'By': Array of tangential field components (Tesla)
            - 'Bz': Array of perpendicular field components (Tesla)
            - 'B_magnitude': Array of field magnitudes (Tesla)
    """
    # Generate rotation angles
    theta_deg = np.linspace(theta_start_deg, theta_end_deg, n_steps, endpoint=False)
    theta_rad = np.deg2rad(theta_deg)
    
    # Initialize field arrays
    Bx_list = np.zeros(n_steps)
    By_list = np.zeros(n_steps)
    Bz_list = np.zeros(n_steps)
    
    # Get sensor position (constant, doesn't change with rotation)
    sensor_pos_mm = sensor.position_at_theta_deg(0.0)
    
    # For each rotation angle, compute total field from all magnets
    for i, theta_i in enumerate(theta_deg):
        B_total = np.zeros(3)
        
        # Sum contributions from all magnets at this angle
        for magnet in magnet_array.magnets:
            # Rotate magnet to current angle
            rotated_magnet = magnet.rotate_z(theta_i)
            
            # Get magnet center in 3D (mm)
            mag_center_mm = rotated_magnet.center_mm
            
            # Compute field contribution from this magnet (Tesla)
            B_mag = compute_field(
                magnet_center_mm=mag_center_mm,
                magnet_dims_mm=rotated_magnet.dims_mm,
                sensor_pos_mm=sensor_pos_mm,
                Br_T=1.45  # Standard N52 magnet remanence
            )
            B_total += B_mag
        
        Bx_list[i] = B_total[0]
        By_list[i] = B_total[1]
        Bz_list[i] = B_total[2]
    
    # Compute magnitude
    B_mag = np.sqrt(Bx_list**2 + By_list**2 + Bz_list**2)
    
    return {
        'theta_deg': theta_deg,
        'theta_rad': theta_rad,
        'Bx': Bx_list,
        'By': By_list,
        'Bz': Bz_list,
        'B_magnitude': B_mag,
    }


def simulate_over_airgaps(
    n_magnets: int = 60,
    magnet_dims_mm: Tuple[float, float, float] = (20.0, 8.0, 1.5),
    magnet_radius_mm: float = 91.6,
    sensor_radius_mm: float = 96.52,
    airgap_mm_list: list = None,
    n_steps: int = 1920,
) -> Dict[float, Dict]:
    """Run simulation across a range of airgaps.
    
    Args:
        n_magnets: Number of magnets in ring (default: 60).
        magnet_dims_mm: [radial, tangential, thickness] dimensions.
        magnet_radius_mm: Radial position of magnet inner radius.
        sensor_radius_mm: Sensor radial distance from disk center.
        airgap_mm_list: List of airgaps to evaluate. Default: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
        n_steps: Angular steps per rotation.
        
    Returns:
        Dictionary mapping airgap_mm -> simulation results dict.
    """
    if airgap_mm_list is None:
        airgap_mm_list = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
    
    results_by_airgap = {}
    
    for airgap_mm in airgap_mm_list:
        # Create magnet array
        array = MagnetArray.uniform_ring(
            n_magnets=n_magnets,
            inner_radius_mm=magnet_radius_mm,
            dims_mm=magnet_dims_mm,
        )
        
        # Create sensor at this airgap
        sensor = Sensor(
            radius_mm=sensor_radius_mm,
            airgap_mm=airgap_mm,
            z_magnet_thickness_mm=magnet_dims_mm[2],
        )
        
        # Run simulation
        results = simulate_full_rotation(array, sensor, n_steps=n_steps)
        results_by_airgap[airgap_mm] = results
        
        print(f"Airgap {airgap_mm:.1f} mm: By amplitude = {(np.max(results['By']) - np.min(results['By']))/2:.4f} T")
    
    return results_by_airgap


if __name__ == "__main__":
    # Quick test: simulate standard encoder wheel across a few airgaps
    print("Encoder wheel magnetic field simulation")
    print("=" * 50)
    
    results = simulate_over_airgaps(
        n_magnets=60,
        magnet_dims_mm=(20.0, 8.0, 1.5),
        magnet_radius_mm=91.6,
        sensor_radius_mm=96.52,
        airgap_mm_list=[1.0, 2.0, 4.0, 6.0],
        n_steps=1920,
    )
    
    print("\nSimulation complete.")
    print(f"Results available for {len(results)} airgaps")
