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
    
    # North pole always at +z; mu sign handled in magnet_to_corners
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
    
    # South pole always at -z; mu sign handled in magnet_to_corners
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
    """All corners (north, south, and optional reflections) with magnetization values.
    
    Stores corner positions and their corresponding magnetization values.
    Provides method to compute magnetic field at a point in space.
    
    Can represent:
    - A single magnet (8 corners: 4 north, 4 south)
    - A single magnet with reflections (16 corners: original + image)
    - An array of magnets (N*8 or N*16 corners)
    """
    
    def __init__(self, positions, mu_values):
        """
        Args:
            positions: (N_corners, 3) array of [x, y, z] positions (mm)
            mu_values: (N_corners,) array of magnetization values
                      North pole corners: +mu
                      South pole corners: -mu (inverted)
                      Image corners: scaled version of above
        """
        self.positions = np.asarray(positions, dtype=float)  # (N_corners, 3)
        self.mu_values = np.asarray(mu_values, dtype=float)   # (N_corners,)
        
        assert self.positions.shape[0] == self.mu_values.shape[0], \
            f"positions ({self.positions.shape[0]}) and mu_values ({self.mu_values.shape[0]}) must match"
    
    def __repr__(self):
        return f"MagnetCorners(corners={self.positions.shape[0]}, mu_range=[{self.mu_values.min():.3f}, {self.mu_values.max():.3f}])"
    
    @staticmethod
    def combine(*corner_sets):
        """Combine multiple MagnetCorners into one.
        
        Args:
            *corner_sets: Variable number of MagnetCorners instances
        
        Returns:
            New MagnetCorners with all corners stacked
        """
        positions_list = [cs.positions for cs in corner_sets]
        mu_values_list = [cs.mu_values for cs in corner_sets]
        
        positions = np.vstack(positions_list)
        mu_values = np.concatenate(mu_values_list)
        
        return MagnetCorners(positions, mu_values)
    
    def add(self, other):
        """Add corners from another MagnetCorners object to this one.
        
        Modifies this object in-place.
        
        Args:
            other: Another MagnetCorners instance
        """
        self.positions = np.vstack([self.positions, other.positions])
        self.mu_values = np.concatenate([self.mu_values, other.mu_values])
    
    def compute_field_at(self, sensor_pos_mm, Br_T=1.45):
        """Compute magnetic field at a sensor position.
        
        Sums dipole field contributions from all corners.
        
        Args:
            sensor_pos_mm: [x, y, z] sensor position in mm
            Br_T: Remanent flux density in Tesla
        
        Returns:
            [Bx, By, Bz] field in Tesla
        """
        sensor_pos_m = np.asarray(sensor_pos_mm) / 1000.0  # convert to meters
        
        B_total = np.zeros(3)
        
        for pos_mm, mu in zip(self.positions, self.mu_values):
            pos_m = pos_mm / 1000.0  # convert to meters
            
            # Vector from corner to sensor
            r_vec = sensor_pos_m - pos_m
            r_mag = np.linalg.norm(r_vec)
            
            if r_mag < 1e-10:
                # Skip if sensor is at corner position
                continue
            
            # Dipole moment: m = mu * (mu_0 / (4*pi)) * Br * V
            # For unit volume and normalized field, we use: m = mu * Br
            mu_0_over_4pi = 1e-7  # SI units
            m_mag = mu * Br_T  # magnetic moment magnitude
            
            # Dipole field: B = (mu_0 / 4*pi) * [3*(m·r_hat)*r_hat - m] / r^3
            r_hat = r_vec / r_mag
            
            # Magnetization direction: mu already encodes sign, moment is always along z
            m_vec = np.array([0.0, 0.0, mu * Br_T])
            
            # 3*(m·r_hat)*r_hat - m
            m_dot_r_hat = np.dot(m_vec, r_hat)
            field_unnormalized = 3.0 * m_dot_r_hat * r_hat - m_vec
            
            # Scale by mu_0 / (4*pi) / r^3
            B_mag = mu_0_over_4pi * field_unnormalized / (r_mag ** 3)
            
            B_total += B_mag
        
        return B_total


def magnet_to_corners(magnet, dx, dz, dtheta, include_images=False,
                      z_steel_surface=0.0, mu_r=5.7):
    """Create MagnetCorners from a single Magnet.
    
    Args:
        magnet: Magnet object with mx, my, mz, mu
        dx: Radial (x-direction) offset in mm
        dz: Vertical (z-direction) offset in mm
        dtheta: Rotation angle around z-axis in degrees
        include_images: Whether to add image dipoles for steel backing
        z_steel_surface: Height of steel surface (mm) for image positioning
        mu_r: Relative permeability of steel
    
    Returns:
        MagnetCorners with magnet corners and optional reflections
    """
    # Get north and south pole corners
    nc, sc = positioned_corners(magnet, dx, dz, dtheta)
    
    # Stack into single array and assign magnetizations
    positions = np.vstack([nc, sc])  # (8, 3)
    mu_north = np.full(4, magnet.mu)
    mu_south = np.full(4, -magnet.mu)  # inverted for south pole
    mu_values = np.concatenate([mu_north, mu_south])
    
    corners = MagnetCorners(positions, mu_values)
    
    # Add image dipoles if requested
    if include_images:
        # Image scaling factor for steel backing
        mu_scale = (mu_r - 1.0) / (mu_r + 1.0)
        
        # Reflect magnet center z-position across steel surface
        z_mag_center = dz  # magnet center z position
        z_image_center = 2 * z_steel_surface - z_mag_center
        
        # Reflect north and south corners
        nc_img = nc.copy()
        sc_img = sc.copy()
        
        # Offset z-coordinates to reflected position
        z_offset_north = nc[:, 2] - dz  # offset from magnet center
        z_offset_south = sc[:, 2] - dz
        
        nc_img[:, 2] = z_image_center + z_offset_north
        sc_img[:, 2] = z_image_center + z_offset_south
        
        # Create image corners
        img_positions = np.vstack([nc_img, sc_img])
        
        mu_img_north = np.full(4, mu_scale * magnet.mu)
        mu_img_south = np.full(4, -mu_scale * magnet.mu)
        
        img_mu_values = np.concatenate([mu_img_north, mu_img_south])
        
        img_corners = MagnetCorners(img_positions, img_mu_values)
        
        # Combine original and image corners
        corners = MagnetCorners.combine(corners, img_corners)
    
    return corners


def array_to_corners(magnet_array, dx_list, dz_list, dtheta_list,
                     include_images=False, z_steel_surface=0.0, mu_r=5.7):
    """Create MagnetCorners from an array of Magnets.
    
    Args:
        magnet_array: Iterable of Magnet objects
        dx_list: Radial offsets for each magnet (mm)
        dz_list: Vertical offsets for each magnet (mm)
        dtheta_list: Rotation angles for each magnet (degrees)
        include_images: Whether to add image dipoles for each magnet
        z_steel_surface: Height of steel surface (mm) for image positioning
        mu_r: Relative permeability of steel
    
    Returns:
        MagnetCorners with all magnets' corners combined
    """
    corner_sets = []
    
    for magnet, dx, dz, dtheta in zip(magnet_array, dx_list, dz_list, dtheta_list):
        corners = magnet_to_corners(magnet, dx, dz, dtheta,
                                   include_images=include_images,
                                   z_steel_surface=z_steel_surface,
                                   mu_r=mu_r)
        corner_sets.append(corners)
    
    return MagnetCorners.combine(*corner_sets)


def magnet_corners_with_reflections(magnet, dx, dz, dtheta,
                                     include_images=False,
                                     z_steel_surface=0.0,
                                     mu_r=5.7):
    """Legacy alias for magnet_to_corners().
    
    Deprecated: Use magnet_to_corners() instead.
    """
    return magnet_to_corners(magnet, dx, dz, dtheta,
                            include_images=include_images,
                            z_steel_surface=z_steel_surface,
                            mu_r=mu_r)



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
