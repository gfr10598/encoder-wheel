#!/usr/bin/env python3
"""
Magnet object and magnet array representation.

Convention:
  - mx: radial dimension (long axis, points outward from disk center)
  - my: tangential dimension (short axis, perpendicular to radius)
  - mz: thickness (vertical, perpendicular to disk plane)
  - Poles are at z = ±mz/2
  - my < mx always
"""

import numpy as np
import math


class Magnet:
    """
    A rectangular magnet with fixed dimensions and orientation.
    
    Attributes:
        mx, my, mz (float): dimensions in mm
        center (np.array): [x, y, z] center position in mm (global frame)
        polarity (int): +1 for north-up, -1 for south-up
        theta_deg (float): angle in degrees (0-360)
    """
    
    def __init__(self, mx, my, mz, center_mm, polarity=1, theta_deg=0):
        """
        Args:
            mx (float): radial dimension (mm)
            my (float): tangential dimension (mm)
            mz (float): thickness (mm)
            center_mm (tuple or array): [x, y, z] center in mm
            polarity (int): +1 or -1
            theta_deg (float): angle in degrees
        """
        assert my < mx, f"my ({my}) must be < mx ({mx})"
        assert polarity in [1, -1], "polarity must be ±1"
        
        self.mx = float(mx)
        self.my = float(my)
        self.mz = float(mz)
        self.center = np.array(center_mm, dtype=float)
        self.polarity = int(polarity)
        self.theta_deg = float(theta_deg)
    
    @property
    def dims_mm(self):
        """Return [mx, my, mz] dimensions."""
        return np.array([self.mx, self.my, self.mz])
    
    @property
    def theta_rad(self):
        """Return angle in radians."""
        return math.radians(self.theta_deg)
    
    @property
    def radius_mm(self):
        """Return radial distance from disk center to magnet center."""
        return np.linalg.norm(self.center[:2])
    
    @property
    def z_min(self):
        """Return minimum z coordinate (lower surface)."""
        return self.center[2] - self.mz / 2.0
    
    @property
    def z_max(self):
        """Return maximum z coordinate (upper surface)."""
        return self.center[2] + self.mz / 2.0
    
    @property
    def r_inner(self):
        """Return inner radial edge (toward disk center)."""
        return self.radius_mm - self.mx / 2.0
    
    @property
    def r_outer(self):
        """Return outer radial edge (away from disk center)."""
        return self.radius_mm + self.mx / 2.0
    
    def __repr__(self):
        r = self.radius_mm
        return (f"Magnet(mx={self.mx}, my={self.my}, mz={self.mz}, "
                f"r={r:.2f}, θ={self.theta_deg:.1f}°, "
                f"pos={self.center}, pol={self.polarity:+d})")
    
    @staticmethod
    def positioned_at_angle(mx, my, mz, theta_deg, polarity=1, 
                           outer_radius_mm=101.6, z_lower=0.0):
        """
        Create a magnet positioned at a given angle with standard placement.
        
        Standard placement:
          - Lower surface at z_lower (default z=0)
          - Outer radial edge at outer_radius_mm (default 8" OD = 101.6 mm)
          - Magnet centered on disk (theta, 0) in radial-tangential frame
        
        Args:
            mx, my, mz (float): dimensions in mm
            theta_deg (float): angle around disk in degrees
            polarity (int): +1 or -1
            outer_radius_mm (float): outer edge radial position (mm)
            z_lower (float): lower surface z position (mm)
        
        Returns:
            Magnet: positioned magnet
        """
        # Radial position: outer edge minus half of mx
        radius_mm = outer_radius_mm - mx / 2.0
        
        # Z position: lower surface plus half of mz
        z_center = z_lower + mz / 2.0
        
        # Convert angle to Cartesian
        theta_rad = math.radians(theta_deg)
        x = radius_mm * math.cos(theta_rad)
        y = radius_mm * math.sin(theta_rad)
        
        return Magnet(
            mx=mx,
            my=my,
            mz=mz,
            center_mm=[x, y, z_center],
            polarity=polarity,
            theta_deg=theta_deg
        )
    
    def rotate_z(self, delta_deg):
        """
        Rotate magnet around z-axis by delta_deg degrees.
        
        This is the second transform: rotates magnet position and orientation.
        
        Args:
            delta_deg (float): rotation angle in degrees
        
        Returns:
            Magnet: new rotated magnet (original unchanged)
        """
        delta_rad = math.radians(delta_deg)
        cos_d = math.cos(delta_rad)
        sin_d = math.sin(delta_rad)
        
        # Rotate center position around z-axis
        x_new = self.center[0] * cos_d - self.center[1] * sin_d
        y_new = self.center[0] * sin_d + self.center[1] * cos_d
        z_new = self.center[2]
        
        new_center = np.array([x_new, y_new, z_new])
        new_theta = self.theta_deg + delta_deg
        
        # Normalize theta to [0, 360)
        new_theta = new_theta % 360.0
        
        return Magnet(
            mx=self.mx,
            my=self.my,
            mz=self.mz,
            center_mm=new_center,
            polarity=self.polarity,
            theta_deg=new_theta
        )


class MagnetArray:
    """
    Array of magnets arranged in a ring.
    
    Attributes:
        magnets (list): list of Magnet objects
        n_magnets (int): number of magnets
    """
    
    def __init__(self, magnets=None):
        """
        Args:
            magnets (list): list of Magnet objects
        """
        self.magnets = magnets if magnets is not None else []
    
    def __len__(self):
        return len(self.magnets)
    
    def __getitem__(self, idx):
        return self.magnets[idx]
    
    def __iter__(self):
        return iter(self.magnets)
    
    def append(self, magnet):
        """Add a magnet to the array."""
        self.magnets.append(magnet)
    
    @staticmethod
    def create_uniform_ring(n_magnets, mx, my, mz, outer_radius_mm=101.6, 
                           z_lower=0.0, alternating_polarity=True):
        """
        Create a uniform ring of magnets with standard positioning.
        
        Standard positioning:
          - Lower surface at z_lower (default 0.0 mm)
          - Outer radial edge at outer_radius_mm (default 101.6 mm for 8" OD)
          - Magnets evenly spaced around disk (angular pitch = 360/n)
          - Optionally alternating polarity (N-S-N-S)
        
        Args:
            n_magnets (int): number of magnets (e.g., 60)
            mx, my, mz (float): magnet dimensions in mm
            outer_radius_mm (float): outer edge radial position (mm)
            z_lower (float): lower surface z position (mm)
            alternating_polarity (bool): whether to alternate polarity
        
        Returns:
            MagnetArray: uniform ring
        """
        array = MagnetArray()
        angular_pitch = 360.0 / n_magnets
        
        for i in range(n_magnets):
            theta_deg = i * angular_pitch
            
            # Alternating polarity (N-S-N-S pattern)
            polarity = 1 if (i % 2 == 0) else -1 if alternating_polarity else 1
            
            magnet = Magnet.positioned_at_angle(
                mx=mx,
                my=my,
                mz=mz,
                theta_deg=theta_deg,
                polarity=polarity,
                outer_radius_mm=outer_radius_mm,
                z_lower=z_lower
            )
            array.append(magnet)
        
        return array
    
    def summary(self):
        """Print summary of array."""
        if len(self.magnets) == 0:
            print("Empty magnet array")
            return
        
        print(f"Magnet Array: {len(self.magnets)} magnets")
        m0 = self.magnets[0]
        print(f"  Dimensions: {m0.mx} × {m0.my} × {m0.mz} mm")
        print(f"  Radius: {m0.radius_mm:.2f} mm")
        
        if len(self.magnets) > 1:
            angular_pitch = 360.0 / len(self.magnets)
            print(f"  Angular pitch: {angular_pitch:.2f}°")
        
        # Count polarity
        n_pos = sum(1 for m in self.magnets if m.polarity > 0)
        n_neg = sum(1 for m in self.magnets if m.polarity < 0)
        print(f"  Polarity: {n_pos} north-up, {n_neg} south-up")


def main():
    """Test magnet and array objects."""
    print("=" * 100)
    print("Magnet Object Test")
    print("=" * 100)
    
    # Single magnet at origin
    m = Magnet(mx=20.0, my=8.0, mz=1.5, center_mm=[0, 0, 0.75])
    print(f"\n{m}")
    print(f"  Dims: {m.dims_mm}")
    print(f"  Edges: r_inner={m.r_inner:.2f}, r_outer={m.r_outer:.2f}")
    print(f"  Z: z_min={m.z_min:.2f}, z_max={m.z_max:.2f}")
    
    # Test Transform 1: Position at angle with standard placement
    print("\n" + "=" * 100)
    print("Transform 1: Position at angle (outer edge at 8\" OD, lower surface at z=0)")
    print("=" * 100)
    
    m_pos = Magnet.positioned_at_angle(
        mx=20.0, my=8.0, mz=1.5,
        theta_deg=0.0,
        polarity=1,
        outer_radius_mm=101.6,
        z_lower=0.0
    )
    print(f"\nAt θ=0°:")
    print(f"  {m_pos}")
    print(f"  Center: {m_pos.center}")
    print(f"  Edges: r_inner={m_pos.r_inner:.2f}, r_outer={m_pos.r_outer:.2f}")
    print(f"  Z: z_min={m_pos.z_min:.2f}, z_max={m_pos.z_max:.2f}")
    
    # Test Transform 2: Rotate z-axis
    print("\n" + "=" * 100)
    print("Transform 2: Rotate around z-axis by 6°")
    print("=" * 100)
    
    m_rotated = m_pos.rotate_z(6.0)
    print(f"\nAfter rotating by 6°:")
    print(f"  {m_rotated}")
    print(f"  Center: {m_rotated.center}")
    print(f"  Radius: {m_rotated.radius_mm:.4f} (should be same)")
    print(f"  Edges: r_inner={m_rotated.r_inner:.2f}, r_outer={m_rotated.r_outer:.2f}")
    print(f"  Z: z_min={m_rotated.z_min:.2f}, z_max={m_rotated.z_max:.2f}")
    
    # Verify rotation preserves radius
    print(f"\nRadius preservation check:")
    print(f"  Original: {m_pos.radius_mm:.10f}")
    print(f"  Rotated:  {m_rotated.radius_mm:.10f}")
    print(f"  Difference: {abs(m_pos.radius_mm - m_rotated.radius_mm):.2e} mm")
    
    # Create uniform ring using standard positioning
    print("\n" + "=" * 100)
    print("Uniform Ring Array (60 magnets)")
    print("=" * 100)
    
    array = MagnetArray.create_uniform_ring(
        n_magnets=60,
        mx=20.0,
        my=8.0,
        mz=1.5,
        outer_radius_mm=101.6,
        z_lower=0.0
    )
    array.summary()
    
    # Show first few magnets
    print("\nFirst 5 magnets:")
    for i in range(min(5, len(array))):
        print(f"  [{i}] θ={array[i].theta_deg:6.1f}°, r_outer={array[i].r_outer:7.2f}, "
              f"pol={array[i].polarity:+d}")
    
    # Verify geometry
    print("\n" + "=" * 100)
    print("Geometry Verification")
    print("=" * 100)
    
    # Check that magnets are evenly spaced
    angles = [m.theta_deg for m in array]
    print(f"\nAngle range: {min(angles):.1f}° to {max(angles):.1f}°")
    
    # Check outer edge alignment
    outer_radii = [m.r_outer for m in array]
    print(f"\nOuter radii (should all be 101.6 mm):")
    print(f"  Min: {min(outer_radii):.6f} mm")
    print(f"  Max: {max(outer_radii):.6f} mm")
    print(f"  Std dev: {np.std(outer_radii):.10f} mm")
    
    # Check lower surface alignment
    z_mins = [m.z_min for m in array]
    print(f"\nLower surfaces (should all be 0.0 mm):")
    print(f"  Min: {min(z_mins):.10f} mm")
    print(f"  Max: {max(z_mins):.10f} mm")
    print(f"  Std dev: {np.std(z_mins):.10f} mm")
    
    # Test rotation of array
    print("\n" + "=" * 100)
    print("Test: Rotate entire array by 3°")
    print("=" * 100)
    
    array_rot = MagnetArray([m.rotate_z(3.0) for m in array])
    
    print(f"\nBefore rotation - first magnet:")
    print(f"  {array[0]}")
    print(f"After rotation - first magnet:")
    print(f"  {array_rot[0]}")
    
    # Verify outer edges still aligned
    outer_radii_rot = [m.r_outer for m in array_rot]
    print(f"\nOuter radii after rotation (should still be 101.6 mm):")
    print(f"  Min: {min(outer_radii_rot):.6f} mm")
    print(f"  Max: {max(outer_radii_rot):.6f} mm")
    print(f"  Std dev: {np.std(outer_radii_rot):.10f} mm")


if __name__ == "__main__":
    main()
