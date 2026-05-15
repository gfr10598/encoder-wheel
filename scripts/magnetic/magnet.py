#!/usr/bin/env python3
"""
Magnet object: raw geometry and magnetization only.

Convention:
  - mx: radial dimension (long axis, points outward from disk center)
  - my: tangential dimension (short axis, perpendicular to radius)
  - mz: thickness (vertical, perpendicular to disk plane)
  - mu: magnetization (positive for north-up, negative for south-up)
  - my < mx always
"""

import numpy as np
import math


class Magnet:
    """
    A rectangular magnet defined by dimensions and magnetization only.
    
    Attributes:
        mx, my, mz (float): dimensions in mm
        mu (float): magnetization (positive or negative)
    """
    
    def __init__(self, mx, my, mz, mu):
        """
        Args:
            mx (float): radial dimension (mm)
            my (float): tangential dimension (mm)
            mz (float): thickness (mm)
            mu (float): magnetization (positive or negative)
        """
        assert my < mx, f"my ({my}) must be < mx ({mx})"
        
        self.mx = float(mx)
        self.my = float(my)
        self.mz = float(mz)
        self.mu = float(mu)
    
    def __repr__(self):
        return f"Magnet(mx={self.mx}, my={self.my}, mz={self.mz}, mu={self.mu:+.2f})"


def north_corners(magnet, radial_offset_mm, theta_deg):
    """Get 4 corners of the north pole surface.
    
    Args:
        magnet (Magnet): magnet geometry and magnetization
        radial_offset_mm (float): radial (x-direction) offset in mm
        theta_deg (float): rotation angle in degrees
    
    Returns:
        (4, 3) array of corner positions [x, y, z] for north pole.
    """
    dx = magnet.mx / 2.0
    dy = magnet.my / 2.0
    dz = magnet.mz / 2.0
    
    # North pole always at +z
    z_pole = dz
    
    # Corners in magnet-local frame
    corners_local = np.array([
        [radial_offset_mm-dx, -dy, z_pole],
        [radial_offset_mm+dx, -dy, z_pole],
        [radial_offset_mm+dx, +dy, z_pole],
        [radial_offset_mm-dx, +dy, z_pole],
    ])
    
    # Apply rotation around z-axis
    theta_rad = math.radians(theta_deg)
    cos_t = np.cos(theta_rad)
    sin_t = np.sin(theta_rad)
    
    x_rot = corners_local[:, 0] * cos_t - corners_local[:, 1] * sin_t
    y_rot = corners_local[:, 0] * sin_t + corners_local[:, 1] * cos_t
    z_rot = corners_local[:, 2]
    
    corners= np.column_stack([x_rot, y_rot, z_rot])
    
    return corners


def south_corners(magnet, radial_offset_mm, theta_deg):
    """Get 4 corners of the south pole surface.
    
    Args:
        magnet (Magnet): magnet geometry and magnetization
        radial_offset_mm (float): radial (x-direction) offset in mm
        theta_deg (float): rotation angle in degrees
    
    Returns:
        (4, 3) array of corner positions [x, y, z] for south pole.
    """
    dx = magnet.mx / 2.0
    dy = magnet.my / 2.0
    dz = magnet.mz / 2.0
    
    # South pole always at -z
    z_pole = -dz
    
    # Corners in magnet-local frame
    corners_local = np.array([
        [radial_offset_mm-dx, -dy, z_pole],
        [radial_offset_mm+dx, -dy, z_pole],
        [radial_offset_mm+dx, +dy, z_pole],
        [radial_offset_mm-dx, +dy, z_pole],
    ])
    
    # Apply rotation around z-axis
    theta_rad = math.radians(theta_deg)
    cos_t = np.cos(theta_rad)
    sin_t = np.sin(theta_rad)
    
    x_rot = corners_local[:, 0] * cos_t - corners_local[:, 1] * sin_t
    y_rot = corners_local[:, 0] * sin_t + corners_local[:, 1] * cos_t
    z_rot = corners_local[:, 2]
    
    corners= np.column_stack([x_rot, y_rot, z_rot])
    
    return corners


def positioned_corners(magnet, dx, dz, dtheta):
    """
    Transform a magnet's corners by translation and rotation.
    
    Transform sequence:
      1. Offset corners in x (radial) by dx
      2. Rotate corners around z-axis by dtheta degrees
      3. Offset corners in z by dz
      4. Return transformed north and south corner arrays
    
    Args:
        magnet (Magnet): magnet geometry and magnetization
        dx (float): radial (x-direction) translation in mm
        dz (float): vertical (z-direction) translation in mm
        dtheta (float): rotation angle around z-axis in degrees
    
    Returns:
        (north_corners, south_corners): two (4, 3) arrays
    """
    # Get corners at origin with zero rotation
    nc = north_corners(magnet, 0.0, 0.0)
    sc = south_corners(magnet, 0.0, 0.0)
    
    # Step 1: Offset in x (radial direction)
    nc = nc + np.array([dx, 0.0, 0.0])
    sc = sc + np.array([dx, 0.0, 0.0])
    
    # Step 2: Rotate around z-axis by dtheta
    theta_rad = math.radians(dtheta)
    cos_t = math.cos(theta_rad)
    sin_t = math.sin(theta_rad)
    
    rotation_matrix = np.array([
        [cos_t, -sin_t, 0.0],
        [sin_t,  cos_t, 0.0],
        [0.0,    0.0,   1.0]
    ])
    
    nc = nc @ rotation_matrix.T
    sc = sc @ rotation_matrix.T
    
    # Step 3: Offset in z (vertical direction)
    nc = nc + np.array([0.0, 0.0, dz])
    sc = sc + np.array([0.0, 0.0, dz])
    
    return nc, sc


class MagnetCorners:
    """All corners (north, south, and optional reflections) with Br values.
    
    Stores corner positions and their corresponding remanent flux density (Br_T) values.
    Provides method to compute magnetic field at a point in space.
    
    Can represent:
    - A single magnet (8 corners: 4 north, 4 south)
    - A single magnet with reflections (16 corners: original + image)
    - An array of magnets (N*8 or N*16 corners)
    """
    
    def __init__(self, positions, br_values):
        """
        Args:
            positions: (N_corners, 3) array of [x, y, z] positions (mm)
            br_values: (N_corners,) array of remanent flux density values (T)
                      North pole corners: +Br
                      South pole corners: -Br (inverted)
                      Image corners: scaled version of above
        """
        self.positions = np.asarray(positions, dtype=float)  # (N_corners, 3)
        self.br_values = np.asarray(br_values, dtype=float)   # (N_corners,)
        
        assert self.positions.shape[0] == self.br_values.shape[0], \
            f"positions ({self.positions.shape[0]}) and br_values ({self.br_values.shape[0]}) must match"
    
    def __repr__(self):
        return f"MagnetCorners(corners={self.positions.shape[0]}, br_range=[{self.br_values.min():.3f}, {self.br_values.max():.3f}] T)"
    
    @staticmethod
    def combine(*corner_sets):
        """Combine multiple MagnetCorners into one.
        
        Args:
            *corner_sets: Variable number of MagnetCorners instances
        
        Returns:
            New MagnetCorners with all corners stacked
        """
        positions_list = [cs.positions for cs in corner_sets]
        br_values_list = [cs.br_values for cs in corner_sets]
        
        positions = np.vstack(positions_list)
        br_values = np.concatenate(br_values_list)
        
        return MagnetCorners(positions, br_values)
    
    def add(self, other):
        """Add corners from another MagnetCorners object to this one.
        
        Modifies this object in-place.
        
        Args:
            other: Another MagnetCorners instance
        """
        self.positions = np.vstack([self.positions, other.positions])
        self.br_values = np.concatenate([self.br_values, other.br_values])
    
    def compute_field_at(self, sensor_pos_mm):
        """Compute magnetic field at sensor_pos_mm using the Aharoni corner-sum formula.

        Each stored corner contributes arctan/log terms to Bz/Bx/By respectively.
        The sign pattern (-1)^(i+j+k) for each corner is pre-encoded in br_values,
        so this method needs no per-magnet bookkeeping at compute time.

        The formula (per corner, with (x,y,z) = sensor - corner in meters):
            Bz += br * arctan2(x*y,  z*r)
            Bx += br * log(y + r)
            By += br * log(x + r)
        Final: Bx = -scale*Bx_sum, By = -scale*By_sum, Bz = scale*Bz_sum
        where scale = 1/(4*pi).  br already encodes sign*Br_T.

        This is equivalent to summing compute_field_analytic() over all magnets,
        but operates on the precomputed and validated corner array.

        Args:
            sensor_pos_mm: [x, y, z] sensor position in mm

        Returns:
            [Bx, By, Bz] field in Tesla
        """
        sensor_m = np.asarray(sensor_pos_mm, dtype=float) / 1000.0
        eps = 1e-12

        Bx_sum = 0.0
        By_sum = 0.0
        Bz_sum = 0.0

        for pos_mm, br in zip(self.positions, self.br_values):
            x, y, z = sensor_m - np.asarray(pos_mm) / 1000.0
            r = np.sqrt(x*x + y*y + z*z)
            if r < 1e-15:
                continue
            Bz_sum += br * np.arctan2(x * y, z * r + eps)
            Bx_sum += br * np.log(max(y + r, eps))
            By_sum += br * np.log(max(x + r, eps))

        scale = 1.0 / (4.0 * np.pi)
        return np.array([-scale * Bx_sum, -scale * By_sum, scale * Bz_sum])
    
    @staticmethod
    def compute_field_analytic(center_mm, dims_mm, sensor_mm, Br_T=1.45):
        """Compute magnetic field using Aharoni rectangular prism formula.
        
        Analytic closed-form solution for uniformly magnetized rectangular magnet.
        
        Args:
            center_mm: [x, y, z] magnet center in mm
            dims_mm: [L, W, T] full magnet dimensions in mm
            sensor_mm: [x, y, z] sensor position in mm
            Br_T: Remanent flux density in Tesla (default 1.45 for N52)
        
        Returns:
            [Bx, By, Bz] field in Tesla
        """
        from magnet_transform import get_magnet_angle, transform_to_magnet_local, transform_to_global

        center = np.array(center_mm, dtype=float) / 1000.0
        sensor = np.array(sensor_mm, dtype=float) / 1000.0
        dims = np.array(dims_mm, dtype=float) / 1000.0

        # Rotate sensor into magnet-local frame so that L always points along
        # local-x (radially outward) regardless of the magnet's position angle.
        theta = get_magnet_angle(center_mm)
        rel_global = sensor - center
        rel_local = transform_to_magnet_local(rel_global, theta)
        dx, dy, dz = rel_local

        L, W, T = dims
        a, b, c = L/2.0, W/2.0, T/2.0

        X = np.array([dx - a, dx + a])
        Y = np.array([dy - b, dy + b])
        Z = np.array([dz - c, dz + c])

        M = Br_T

        Bz_sum = 0.0
        Bx_sum = 0.0
        By_sum = 0.0

        # Corner-sum formula: iterate over 8 corners of rectangular magnet
        for i in range(2):
            for j in range(2):
                for k in range(2):
                    x = X[i]
                    y = Y[j]
                    z = Z[k]

                    r = np.sqrt(x**2 + y**2 + z**2)
                    if r < 1e-12:
                        continue

                    # Sign pattern for corner contributions
                    sgn = (-1.0)**(i + j + k)

                    # Aharoni corner-sum components
                    Bz_sum += sgn * np.arctan2(x*y, z*r)
                    Bx_sum += sgn * np.log(max(y + r, 1e-12))
                    By_sum += sgn * np.log(max(x + r, 1e-12))

        scale = M / (4*np.pi)

        # Field in magnet-local frame; rotate Bx/By back to global frame.
        B_local = np.array([-scale * Bx_sum, -scale * By_sum, scale * Bz_sum])
        return transform_to_global(B_local, theta)


class MagnetArray:
    """Array of magnets."""
    
    def __init__(self, magnets=None):
        self.magnets = magnets if magnets is not None else []
    
    def __len__(self):
        return len(self.magnets)
    
    def __getitem__(self, idx):
        return self.magnets[idx]
    
    def __iter__(self):
        return iter(self.magnets)
    
    def append(self, magnet):
        self.magnets.append(magnet)
