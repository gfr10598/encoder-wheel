"""Unit tests for Magnet and MagnetArray classes."""

import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from magnet import Magnet, MagnetArray, north_corners, south_corners, positioned_corners


def test_magnet_creation():
    """Test basic magnet creation."""
    print("TEST: Magnet Creation")
    print("-" * 70)
    
    # Create a magnet with north-up (mu > 0)
    m = Magnet(mx=10.0, my=5.0, mz=1.0, mu=+1.0)
    
    assert m.mx == 10.0
    assert m.my == 5.0
    assert m.mz == 1.0
    assert m.mu == 1.0
    
    print("✓ Basic magnet creation (north-up)")
    print(f"  {m}")
    
    # Create a magnet with south-up (mu < 0)
    m2 = Magnet(mx=20.0, my=8.0, mz=1.5, mu=-1.45)
    
    assert m2.mx == 20.0
    assert m2.my == 8.0
    assert m2.mz == 1.5
    assert m2.mu == -1.45
    
    print("✓ Basic magnet creation (south-up)")
    print(f"  {m2}")
    print()


def test_magnet_dimensions():
    """Test magnet dimension constraints."""
    print("TEST: Magnet Dimension Constraints")
    print("-" * 70)
    
    # my must be < mx
    try:
        bad_magnet = Magnet(mx=5.0, my=10.0, mz=1.0, mu=1.0)
        assert False, "Should have rejected my >= mx"
    except AssertionError as e:
        if "my" in str(e):
            print("✓ Correctly rejects my >= mx")
        else:
            raise
    
    print()


def test_corner_computation():
    """Test corner computation functions."""
    print("TEST: Corner Computation Functions")
    print("-" * 70)
    
    m = Magnet(mx=10.0, my=5.0, mz=1.0, mu=+1.0)
    
    # Get corners at origin with north-up (mu=+1)
    nc = north_corners(m, radial_offset_mm=0.0, theta_deg=0.0)
    sc = south_corners(m, radial_offset_mm=0.0, theta_deg=0.0)
    
    print(f"North corners (north-up, mu=+1.0):")
    print(f"  {nc}")
    print(f"South corners (north-up, mu=+1.0):")
    print(f"  {sc}")
    
    # North pole should be at +z_pole = +0.5 mm
    assert np.allclose(nc[:, 2], +0.5), "North pole z should be +0.5"
    # South pole should be at -z_pole = -0.5 mm  
    assert np.allclose(sc[:, 2], -0.5), "South pole z should be -0.5"
    
    print("✓ North-up magnetization correct")
    
    # Now test south-up (mu=-1)
    m2 = Magnet(mx=10.0, my=5.0, mz=1.0, mu=-1.0)
    nc2 = north_corners(m2, radial_offset_mm=0.0, theta_deg=0.0)
    sc2 = south_corners(m2, radial_offset_mm=0.0, theta_deg=0.0)
    
    print(f"North corners (south-up, mu=-1.0):")
    print(f"  {nc2}")
    print(f"South corners (south-up, mu=-1.0):")
    print(f"  {sc2}")
    
    # North pole should be at -z_pole = -0.5 mm (flipped)
    assert np.allclose(nc2[:, 2], -0.5), "North pole z should be -0.5"
    # South pole should be at +z_pole = +0.5 mm (flipped)
    assert np.allclose(sc2[:, 2], +0.5), "South pole z should be +0.5"
    
    print("✓ South-up magnetization correct")
    print()


def test_positioned_corners_transform():
    """Test positioned_corners() transformation sequence."""
    print("TEST: Transform Sequence (offset → rotate → offset in z)")
    print("-" * 70)
    
    m = Magnet(mx=10.0, my=5.0, mz=1.0, mu=+1.0)
    
    # Position at radius 10 mm, height 0.5 mm, angle 0°
    nc, sc = positioned_corners(m, dx=10.0, dz=0.5, dtheta=0.0)
    
    print(f"Positioned corners at (dx=10, dz=0.5, dtheta=0°):")
    print(f"  North: {nc}")
    print(f"  South: {sc}")
    
    # Check radial offsets: corners should span [10-5, 10+5] = [5, 15] in x
    assert np.allclose(nc[:, 0].min(), 5.0, atol=1e-10), f"x_min should be 5, got {nc[:, 0].min()}"
    assert np.allclose(nc[:, 0].max(), 15.0, atol=1e-10), f"x_max should be 15, got {nc[:, 0].max()}"
    
    # Check z positions
    assert np.allclose(nc[:, 2], 1.0), f"North z should be 1.0 (0.5 + 0.5), got {nc[:, 2]}"
    assert np.allclose(sc[:, 2], 0.0), f"South z should be 0.0 (0.5 - 0.5), got {sc[:, 2]}"
    


def test_magnet_array():
    """Test MagnetArray basic operations."""
    print("TEST: MagnetArray")
    print("-" * 70)
    
    array = MagnetArray()
    
    # Add magnets
    m1 = Magnet(mx=10.0, my=5.0, mz=1.0, mu=+1.0)
    m2 = Magnet(mx=10.0, my=5.0, mz=1.0, mu=-1.0)
    m3 = Magnet(mx=20.0, my=8.0, mz=1.5, mu=+1.45)
    
    array.append(m1)
    array.append(m2)
    array.append(m3)
    
    # Test length
    assert len(array) == 3, f"Expected 3 magnets, got {len(array)}"
    
    # Test indexing
    assert array[0] is m1
    assert array[1] is m2
    assert array[2] is m3
    
    # Test iteration
    magnets = list(array)
    assert len(magnets) == 3
    assert magnets[0] is m1
    
    print("✓ MagnetArray works correctly")
    print(f"  Length: {len(array)}")
    print(f"  Iteration: {len(list(array))} magnets")
    print()


def run_all_tests():
    """Run all unit tests."""
    print("=" * 70)
    print("MAGNET AND MAGNET ARRAY UNIT TESTS")
    print("=" * 70)
    print()
    
    tests = [
        test_magnet_creation,
        test_magnet_dimensions,
        test_corner_computation,
        test_positioned_corners_transform,
        test_magnet_array,
    ]
    
    failed = []
    for test in tests:
        try:
            test()
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

