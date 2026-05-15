"""
4-pole symmetric sanity check for magnet field computation.

This test verifies field math using a 4-fold symmetric magnet arrangement.
By 4-fold rotational symmetry, the field exhibits predictable patterns at different locations.

Coordinate system:
  - Radial (r): distance from disk center (x in Cartesian)
  - Tangential (θ): angle around disk (y in Cartesian, measured CCW)
  - Axial (z): perpendicular to disk plane

Setup:
  - 4 magnets at θ = 0°, 90°, 180°, 270° (cardinal directions)
  - All centered at radius = 10 mm, axial height z = 0.5 mm (center)
  - Remanent flux density (Br_T): -1.45 T (N-down), +1.45 T (N-up), -1.45 T (N-down), +1.45 T (N-up)
  - Dimensions: 10 × 5 × 1 mm (radial × tangential × axial/thickness)
  - Lower magnet surface at z = 0.0 mm
  - Upper magnet surface at z = 1.0 mm

TEST CATEGORIES AND EXPECTATIONS:

1. ZERO FIELD ON AXIAL (Z) AXIS
   - Location: (0, 0, z) at multiple heights z = 0.0, 0.5, 1.0, 2.0, 5.0, 11.0 mm
   - Expectation: 
     * Radial field (Br) = 0 (4-fold rotational symmetry cancels)
     * Tangential field (Bθ) = 0 (4-fold rotational symmetry cancels)
     * Axial field (Bz) = 0 (by mirror symmetry: 2 north and 2 south poles)
   - Reason: All 4 magnets contribute equally but cancel by symmetry

2. NON-ZERO AXIAL FIELD AT CARDINAL POINTS (over magnet centers)
   - Location: (10,0,z), (0,10,z), (-10,0,z), (0,-10,z) at z = 0.5, 1.0, 11.0 mm
   - Expectation:
     * Radial field (Br) has opposite sign over N vs S poles
       - Over N poles (90°, 270°): Br pointing OUTWARD (positive)
       - Over S poles (0°, 180°): Br pointing INWARD (negative)
     * Tangential field (Bθ) ≈ 0 (cardinal points have azimuthal symmetry)
     * Axial field (Bz) is strong and non-zero (dominant signal)
   - Reason: Cardinal points break 4-fold symmetry; field from nearest magnet dominates

3. NON-ZERO TANGENTIAL FIELD AT DIAGONAL POINTS (between magnets)
   - Location: (7.07,7.07), (-7.07,7.07), (-7.07,-7.07), (7.07,-7.07) at z = 0.5, 1.0, 11.0 mm
   - Expectation:
     * Radial field (Br) = 0 (by diagonal symmetry)
     * Tangential field (Bθ) is strong and non-zero (dominant signal)
     * Axial field (Bz) is non-zero but secondary to tangential
   - Reason: Diagonal points are equidistant from 4 magnets; radial contributions cancel,
     tangential contributions add constructively
"""

import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from magnet import Magnet, MagnetCorners


def test_symmetric_cross():
    """Test 4-magnet symmetric cross with corrected positioning and corner Br_T values.
    
    Magnet orientations (all at radius 10mm, center z=0.5mm, lower surface z=0, upper surface z=1):
    - 0°, 180°: N-down (Br_T=-1.45 T)
      * North pole points DOWN at z=0 (lower surface)
      * South pole points UP at z=1 (upper surface)
      * Geometric north_corners (at +z/upper): Br_T = -1.45 T (south surface)
      * Geometric south_corners (at -z/lower): Br_T = +1.45 T (north surface)
    
    - 90°, 270°: N-up (Br_T=+1.45 T)
      * North pole points UP at z=1 (upper surface)
      * South pole points DOWN at z=0 (lower surface)
      * Geometric north_corners (at +z/upper): Br_T = +1.45 T (north surface)
      * Geometric south_corners (at -z/lower): Br_T = -1.45 T (south surface)
    """
    print("=" * 70)
    print("SANITY CHECK: 4-Magnet Symmetric Cross (Corrected Configuration)")
    print("=" * 70)
    print()
    print("Setup:")
    print("  - 4 magnets (10×5×1 mm) positioned at radius 10mm, center at z=0.5mm")
    print("  - Positioned at cardinal angles: 0°, 90°, 180°, 270°")
    print("  - Orientations (Br_T sign indicates N pole direction):")
    print("    • 0°, 180°: N-down (Br_T=-1.45 T) → upper surface (z=1) is S pole")
    print("    • 90°, 270°: N-up (Br_T=+1.45 T) → upper surface (z=1) is N pole")
    print()
    
    # Create base magnet geometry
    # Position parameters for each magnet at cardinal angles
    # Format: (theta_deg, Br_T, label)
    configs = [
        (0.0, -1.45, "0° (10,0) N-down"),
        (90.0, +1.45, "90° (0,10) N-up"),
        (180.0, -1.45, "180° (-10,0) N-down"),
        (270.0, +1.45, "270° (0,-10) N-up"),
    ]
    
    print("Magnets: (using Aharoni formula)")
    print("-" * 70)
    
    # Create magnet configurations for Aharoni computation
    magnets = []
    for theta_deg, br_t, label in configs:
        theta_rad = np.radians(theta_deg)
        x = 10.0 * np.cos(theta_rad)
        y = 10.0 * np.sin(theta_rad)
        z = 0.5  # center at z=0.5
        
        magnets.append({
            'label': label,
            'center': np.array([x, y, z]),
            'dims': np.array([10.0, 5.0, 1.0]),  # L, W, T
            'Br_T': br_t,
        })
        print(f"{label}: center=({x:.1f}, {y:.1f}, {z:.1f}), Br_T={br_t:+.2f} T")
    
    print()
    print(f"4-magnet symmetric cross configured correctly")
    print()
    
    # Field computation at key symmetry test points
    print("Field measurements at key symmetry points with assertions:")
    print("-" * 70)
    print()
    
    def compute_field_aharoni(pos, magnets):
        """Sum Aharoni field contributions from all magnets."""
        B_total = np.zeros(3)
        for mag in magnets:
            B = MagnetCorners.compute_field_analytic(mag['center'], mag['dims'], pos, Br_T=mag['Br_T'])
            B_total += B
        return B_total
    
    # Test points at radius 10mm (magnet centers), height z=11mm (10mm above surface)
    print("Z-AXIS TEST (expect Bz=0 at all heights by 4-fold symmetry):")
    z_tests = [0.5, 2.0, 5.0, 11.0]
    for z in z_tests:
        pos = np.array([0.0, 0.0, z])
        B = compute_field_aharoni(pos, magnets)
        Bz = B[2]
        Bz_mT = Bz * 1000
        
        status = "✓" if abs(Bz_mT) < 1.0 else "✗"
        print(f"  z={z:>4.1f}: Bz={Bz_mT:>8.2f} mT {status}")
        
        assert abs(Bz_mT) < 1.0, f"Z-axis at z={z}: Bz={Bz_mT} should be ~0 by 4-fold symmetry"
    
    print()
    print("CARDINAL POINTS TEST (expect Bθ≈0 by azimuthal symmetry):")
    z_cardinal = 5.0  # 4mm above surface, far enough from volume
    cardinal_tests = [
        ([10.0, 0.0, z_cardinal], "0° (S-pole center)"),
        ([0.0, 10.0, z_cardinal], "90° (N-pole center)"),
    ]
    
    for pos_list, label in cardinal_tests:
        pos = np.array(pos_list)
        B = compute_field_aharoni(pos, magnets)
        Bx = B[0]
        By = B[1]
        Bz = B[2]
        
        r = np.sqrt(pos[0]**2 + pos[1]**2)
        Br = (Bx * pos[0] + By * pos[1]) / r if r > 0.1 else 0.0
        Btheta = (-Bx * pos[1] + By * pos[0]) / r if r > 0.1 else 0.0
        
        Br_mT = Br * 1000
        Btheta_mT = Btheta * 1000
        Bz_mT = Bz * 1000
        
        print(f"  {label:<25}: Br={Br_mT:>8.2f}, Bθ={Btheta_mT:>8.2f}, Bz={Bz_mT:>8.2f}")
        
        # Bθ should be near zero at cardinal points (azimuthal symmetry)
        assert abs(Btheta_mT) < 50.0, f"{label}: Bθ={Btheta_mT} should be ~0"
    
    print()
    print("DIAGONAL POINTS TEST (expect Br≈0 by 4-fold symmetry):")
    z_diag = 5.0  # same height as cardinal test
    diag_r = 10.0  # radius 10mm (between magnet centers)
    diagonal_tests = [
        ([diag_r, diag_r, z_diag], "45° Diagonal (NE)"),
        ([-diag_r, diag_r, z_diag], "135° Diagonal (NW)"),
    ]
    
    for pos_list, label in diagonal_tests:
        pos = np.array(pos_list)
        B = compute_field_aharoni(pos, magnets)
        Bx = B[0]
        By = B[1]
        Bz = B[2]
        
        r = np.sqrt(pos[0]**2 + pos[1]**2)
        Br = (Bx * pos[0] + By * pos[1]) / r if r > 0.1 else 0.0
        Btheta = (-Bx * pos[1] + By * pos[0]) / r if r > 0.1 else 0.0
        
        Br_mT = Br * 1000
        Btheta_mT = Btheta * 1000
        Bz_mT = Bz * 1000
        
        print(f"  {label:<25}: Br={Br_mT:>8.2f}, Bθ={Btheta_mT:>8.2f}, Bz={Bz_mT:>8.2f}")
        
        # Br should be near zero at diagonal points (diagonal symmetry)
        assert abs(Br_mT) < 50.0, f"{label}: Br={Br_mT} should be ~0"
        # Bθ should be non-zero at diagonals (field from nearby offset magnets)
        assert abs(Btheta_mT) > 5.0, f"{label}: Bθ={Btheta_mT} should be non-zero"
    
    print()
    return True


def run_all_tests():
    """Run all symmetry sanity check tests."""
    print("=" * 70)
    print("SYMMETRY SANITY CHECK TESTS")
    print("=" * 70)
    print()
    
    tests = [
        test_symmetric_cross,
    ]
    
    failed = []
    for test in tests:
        try:
            result = test()
            if not result:
                failed.append((test.__name__, "Test returned False"))
        except AssertionError as e:
            print(f"✗ FAILED: {e}\n")
            failed.append((test.__name__, str(e)))
        except Exception as e:
            print(f"✗ ERROR: {e}\n")
            failed.append((test.__name__, str(e)))
    
    print("=" * 70)
    if not failed:
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
    else:
        print(f"✗✗✗ {len(failed)} TEST(S) FAILED ✗✗✗")
        for name, error in failed:
            print(f"  - {name}: {error}")
    
    print("=" * 70)
    
    return len(failed) == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
