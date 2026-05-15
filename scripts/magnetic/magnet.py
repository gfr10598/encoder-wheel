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
        """Compute magnetic field at a sensor position using Aharoni algorithm.
        
        Sums corner dipole contributions from all corners using their stored Br values.
        
        Args:
            sensor_pos_mm: [x, y, z] sensor position in mm
        
        Returns:
            [Bx, By, Bz] field in Tesla
        """
        sensor_pos_m = np.asarray(sensor_pos_mm) / 1000.0  # convert to meters
        
        B_total = np.zeros(3)
        
        # Aharoni corner-sum algorithm: each corner is a dipole with its own Br value
        for pos_mm, Br_T in zip(self.positions, self.br_values):
            pos_m = pos_mm / 1000.0  # convert to meters
            
            # Vector from corner to sensor
            r_vec = sensor_pos_m - pos_m
            r_mag = np.linalg.norm(r_vec)
            
            if r_mag < 1e-10:
                # Skip if sensor is at corner position
                continue
            
            # Dipole field formula: B = (mu_0 / 4*pi) * [3*(m·r_hat)*r_hat - m] / r^3
            mu_0_over_4pi = 1e-7  # SI units
            
            r_hat = r_vec / r_mag
            
            # Magnetic moment: m = [0, 0, Br_T] (z-axis magnetization)
            m_vec = np.array([0.0, 0.0, Br_T])
            
            # 3*(m·r_hat)*r_hat - m
            m_dot_r_hat = np.dot(m_vec, r_hat)
            field_unnormalized = 3.0 * m_dot_r_hat * r_hat - m_vec
            
            # Scale by mu_0 / (4*pi) / r^3
            B_contribution = mu_0_over_4pi * field_unnormalized / (r_mag ** 3)
            
            B_total += B_contribution
        
        return B_total
    
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
        center = np.array(center_mm, dtype=float) / 1000.0
        sensor = np.array(sensor_mm, dtype=float) / 1000.0
        dims = np.array(dims_mm, dtype=float) / 1000.0
        
        rel_pos = sensor - center
        dx, dy, dz = rel_pos
        
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
        
        Bz = scale * Bz_sum
        Bx = -scale * Bx_sum
        By = -scale * By_sum
        
        return np.array([Bx, By, Bz])


def magnet_to_corners(magnet, dx, dz, dtheta, Br_T=1.45, include_images=False,
                      z_steel_surface=0.0, mu_r=5.7):
    """Create MagnetCorners from a single Magnet.
    
    Args:
        magnet: Magnet object with mx, my, mz, mu
        dx: Radial (x-direction) offset in mm
        dz: Vertical (z-direction) offset in mm
        dtheta: Rotation angle around z-axis in degrees
        Br_T: Remanent flux density in Tesla (default 1.45 for N52)
        include_images: Whether to add image dipoles for steel backing
        z_steel_surface: Height of steel surface (mm) for image positioning
        mu_r: Relative permeability of steel
    
    Returns:
        MagnetCorners with magnet corners and optional reflections
    """
    # Get north and south pole corners
    nc, sc = positioned_corners(magnet, dx, dz, dtheta)
    
    # Stack into single array and assign remanent flux density values
    positions = np.vstack([nc, sc])  # (8, 3)
    # magnet.mu is the sign: +1 for N-up, -1 for N-down
    br_north = np.full(4, magnet.mu * Br_T)  # N pole gets +Br or -Br
    br_south = np.full(4, -magnet.mu * Br_T)  # S pole gets inverted sign
    br_values = np.concatenate([br_north, br_south])
    
    corners = MagnetCorners(positions, br_values)
    
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
        
        br_img_north = np.full(4, mu_scale * magnet.mu * Br_T)
        br_img_south = np.full(4, -mu_scale * magnet.mu * Br_T)
        
        img_br_values = np.concatenate([br_img_north, br_img_south])
        
        img_corners = MagnetCorners(img_positions, img_br_values)
        
        # Combine original and image corners
        corners = MagnetCorners.combine(corners, img_corners)
    
    return corners


def array_to_corners(magnet_array, dx_list, dz_list, dtheta_list, Br_T=1.45,
                     include_images=False, z_steel_surface=0.0, mu_r=5.7):
    """Create MagnetCorners from an array of Magnets.
    
    Args:
        magnet_array: Iterable of Magnet objects
        dx_list: Radial offsets for each magnet (mm)
        dz_list: Vertical offsets for each magnet (mm)
        dtheta_list: Rotation angles for each magnet (degrees)
        Br_T: Remanent flux density in Tesla (default 1.45 for N52)
        include_images: Whether to add image dipoles for each magnet
        z_steel_surface: Height of steel surface (mm) for image positioning
        mu_r: Relative permeability of steel
    
    Returns:
        MagnetCorners with all magnets' corners combined
    """
    corner_sets = []
    
    for magnet, dx, dz, dtheta in zip(magnet_array, dx_list, dz_list, dtheta_list):
        corners = magnet_to_corners(magnet, dx, dz, dtheta, Br_T=Br_T,
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
