#!/usr/bin/env python3
"""
Single N52 magnet validation: compare against K&J website result (79 gauss).
Uses the Aharoni rectangular prism formula via MagnetCorners class.
"""

import sys
sys.path.insert(0, '/Users/gfr/dev/encoder-wheel/scripts')

from magnet import MagnetCorners
import numpy as np


def test_single_magnet():
    """Test single N52 magnet field vs K&J website."""
    
    print("=" * 70)
    print("SINGLE N52 MAGNET VALIDATION (K&J WEBSITE)")
    print("=" * 70)
    print()
    
    # N52 magnet: 20×8×1.5 mm
    magnet_dims_mm = [20.0, 8.0, 1.5]  # [L, W, T] in mm
    
    # Magnet positioned at origin (0, 0, 0)
    # Center at z = 0.75 mm (half height)
    magnet_center_mm = [0.0, 0.0, magnet_dims_mm[2] / 2]
    
    print("Magnet geometry:")
    print(f"  Dimensions: {magnet_dims_mm[0]} × {magnet_dims_mm[1]} × {magnet_dims_mm[2]} mm (L×W×H)")
    print(f"  Center: ({magnet_center_mm[0]}, {magnet_center_mm[1]}, {magnet_center_mm[2]}) mm")
    print()
    
    # Sensor: 10 mm above N pole surface
    # N pole surface at z = magnet_height = 1.5 mm
    # Sensor at z = 1.5 + 10 = 11.5 mm
    sensor_z_mm = magnet_dims_mm[2] + 10.0
    sensor_pos_mm = [0.0, 0.0, sensor_z_mm]
    
    print(f"Measurement point:")
    print(f"  10 mm above N pole surface")
    print(f"  Position: (0, 0, {sensor_z_mm}) mm")
    print()
    
    # Compute field using Aharoni formula via MagnetCorners
    try:
        B_field = MagnetCorners.compute_field_analytic(magnet_center_mm, magnet_dims_mm, sensor_pos_mm, Br_T=1.45)
        
        Bx_G = B_field[0] * 10000
        By_G = B_field[1] * 10000
        Bz_G = B_field[2] * 10000
        B_mag = np.sqrt(Bx_G**2 + By_G**2 + Bz_G**2)
        
        print("Calculated field (Aharoni formula):")
        print(f"  Bx: {Bx_G:>10.2f} Gauss")
        print(f"  By: {By_G:>10.2f} Gauss")
        print(f"  Bz: {Bz_G:>10.2f} Gauss")
        print(f"  |B|: {B_mag:>10.2f} Gauss")
        print()
        
        print("Validation against K&J website:")
        print(f"  Expected (K&J):  79 Gauss")
        print(f"  Calculated (Bz): {Bz_G:.2f} Gauss")
        error_pct = 100 * abs(Bz_G - 79.0) / 79.0
        print(f"  Error: {abs(Bz_G - 79.0):.2f} Gauss ({error_pct:.1f}%)")
        print()
        
        if error_pct < 10.0:
            print(f"✓ PASS: Within 10% tolerance")
            return True
        else:
            print(f"✗ FAIL: Outside 10% tolerance ({error_pct:.1f}%)")
            return False
            
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_single_magnet()
    sys.exit(0 if success else 1)
