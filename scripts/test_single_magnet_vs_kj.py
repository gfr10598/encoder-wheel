#!/usr/bin/env python3
"""
Single magnet validation test: compare calculated field against K&J website result.

Test setup:
- Single N52 magnet: 20×8×1.5 mm
- Measurement point: 10 mm directly above N pole (at height = magnet_top + 10mm)
- Expected result (K&J website): 79 gauss
"""

import sys
import numpy as np

# Add scripts directory to path for imports
sys.path.insert(0, '/Users/gfr/dev/encoder-wheel/scripts')

from analysis_utils import analytic_rect_prism_B

def test_single_n52_magnet():
    """
    Validate single N52 magnet field calculation against K&J website.
    """
    print("=" * 75)
    print("SINGLE MAGNET VALIDATION TEST")
    print("=" * 75)
    print()
    
    # N52 magnet parameters
    magnet_length = 20.0  # mm, radial extent
    magnet_width = 8.0    # mm, tangential extent
    magnet_height = 1.5   # mm, vertical extent
    
    # Magnet positioned at center (0, 0), N pole facing up
    # Center at z = 0.75 mm (half height)
    magnet_center_mm = [0.0, 0.0, magnet_height / 2]
    magnet_dims_mm = [magnet_length, magnet_width, magnet_height]
    
    # Magnetization axis: +Z (north pole up)
    axis = [0, 0, 1]
    
    print("Magnet Configuration:")
    print(f"  Dimensions: {magnet_length} × {magnet_width} × {magnet_height} mm (L×W×H)")
    print(f"  Material: N52 (Br = 1.45 T)")
    print(f"  Center position: (0, 0, {magnet_height/2}) mm")
    print(f"  Orientation: N pole facing UP (+Z)")
    print()
    
    # Measurement point: 10 mm directly above N pole
    # N pole surface is at z = magnet_height = 1.5 mm
    # Sensor is at z = 1.5 + 10.0 = 11.5 mm
    measurement_height = magnet_height + 10.0
    measurement_point = [0.0, 0.0, measurement_height]
    
    print(f"Measurement Point:")
    print(f"  Location: (0, 0, {measurement_height}) mm")
    print(f"  Distance above N pole: 10 mm")
    print()
    
    # Compute field using analytic rectangular prism formula
    B_field = analytic_rect_prism_B(magnet_center_mm, magnet_dims_mm, axis, measurement_point, Br=1.45)
    
    Bx = B_field[0]
    By = B_field[1]
    Bz = B_field[2]
    
    # Convert to Gauss (1 T = 10,000 Gauss)
    Bx_gauss = Bx * 10000
    By_gauss = By * 10000
    Bz_gauss = Bz * 10000
    
    # Total field magnitude
    B_total_gauss = np.sqrt(Bx_gauss**2 + By_gauss**2 + Bz_gauss**2)
    
    print("Field Components:")
    print(f"  Bx (radial):       {Bx_gauss:>10.2f} Gauss")
    print(f"  By (tangential):   {By_gauss:>10.2f} Gauss")
    print(f"  Bz (perpendicular):{Bz_gauss:>10.2f} Gauss")
    print(f"  |B| (total):       {B_total_gauss:>10.2f} Gauss")
    print()
    
    # Since magnet is centered and measurement is directly above, Bx and By should be ~0
    # Bz should be the dominant component (N pole field pointing up)
    
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
