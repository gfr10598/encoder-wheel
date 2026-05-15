#!/usr/bin/env python3
"""
Single magnet validation test: compare calculated field against K&J website result.

Test setup:
- Single N52 magnet: 10×5×1 mm
- Measurement point: 10 mm directly above N pole (at height = magnet_top + 10mm)
- Expected result (K&J website): 79 gauss
"""

import sys
sys.path.insert(0, '/Users/gfr/dev/encoder-wheel/scripts')

from magnet import MagnetCorners
import numpy as np

def test_single_n52_magnet():
    """
    Validate single N52 magnet field calculation against K&J website.
    """
    print("=" * 75)
    print("SINGLE MAGNET VALIDATION TEST (K&J REFERENCE)")
    print("=" * 75)
    print()
    
    # N52 magnet parameters: 10×5×1 mm
    magnet_dims_mm = [10.0, 5.0, 1.0]  # [L, W, H] in mm
    magnet_center_mm = [0.0, 0.0, magnet_dims_mm[2] / 2]
    
    print("Magnet Configuration:")
    print(f"  Dimensions: {magnet_dims_mm[0]} × {magnet_dims_mm[1]} × {magnet_dims_mm[2]} mm (L×W×H)")
    print(f"  Material: N52 (Br = 1.45 T)")
    print(f"  Center position: (0, 0, {magnet_center_mm[2]}) mm")
    print(f"  Orientation: N pole facing UP (+Z)")
    print()
    
    # Measurement point: 10 mm directly above N pole
    sensor_z_mm = magnet_dims_mm[2] + 10.0
    sensor_pos_mm = [0.0, 0.0, sensor_z_mm]
    
    print(f"Measurement Point:")
    print(f"  Location: (0, 0, {sensor_z_mm}) mm")
    print(f"  Distance above N pole: 10 mm")
    print()
    
    # Compute field using Aharoni formula via MagnetCorners
    B_field = MagnetCorners.compute_field_analytic(magnet_center_mm, magnet_dims_mm, sensor_pos_mm, Br_T=1.45)
    
    Bx_gauss = B_field[0] * 10000
    By_gauss = B_field[1] * 10000
    Bz_gauss = B_field[2] * 10000
    B_total_gauss = np.sqrt(Bx_gauss**2 + By_gauss**2 + Bz_gauss**2)
    
    print("Field Components:")
    print(f"  Bx (radial):       {Bx_gauss:>10.2f} Gauss")
    print(f"  By (tangential):   {By_gauss:>10.2f} Gauss")
    print(f"  Bz (perpendicular):{Bz_gauss:>10.2f} Gauss")
    print(f"  |B| (total):       {B_total_gauss:>10.2f} Gauss")
    print()
    
    print("Validation:")
    print(f"  K&J Website Result: 79 Gauss")
    print(f"  Our Result (Bz):    {Bz_gauss:.2f} Gauss")
    print(f"  Difference:         {abs(Bz_gauss - 79.0):.2f} Gauss ({100*abs(Bz_gauss - 79.0)/79.0:.1f}%)")
    print()
    
    # Check symmetry: Bx and By should be near zero
    print("Symmetry Checks:")
    if abs(Bx_gauss) < 0.1 and abs(By_gauss) < 0.1:
        print("  ✓ Bx ≈ 0 and By ≈ 0 (correct by symmetry)")
    else:
        print(f"  ✗ Bx = {Bx_gauss:.2f}, By = {By_gauss:.2f} (should be ~0)")
    print()
    
    # Success criteria: within ~10% of K&J result
    error_pct = 100 * abs(Bz_gauss - 79.0) / 79.0
    if error_pct < 10.0:
        print(f"✓ PASS: Field matches K&J result within {error_pct:.1f}%")
        return True
    else:
        print(f"✗ FAIL: Field differs from K&J result by {error_pct:.1f}% (>10%)")
        return False

if __name__ == '__main__':
    success = test_single_n52_magnet()
    sys.exit(0 if success else 1)
