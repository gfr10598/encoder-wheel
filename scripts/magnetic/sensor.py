"""Sensor model for encoder wheel magnetic field measurement.

Defines sensor position, measurement conventions, and field integration.
"""

import numpy as np


class Sensor:
    """Fixed magnetic field sensor on encoder wheel stator.
    
    Coordinate system:
      - x: radial (outward from disk center)
      - y: tangential (CCW when viewed from above)
      - z: perpendicular to disk (upward)
    
    Sensor is at a fixed radial distance from disk center, at height above disk surface.
    Magnet disk rotates while sensor remains stationary.
    """
    
    def __init__(self, radius_mm: float, airgap_mm: float, z_magnet_thickness_mm: float = 1.5):
        """Initialize sensor at fixed radial position.
        
        Args:
            radius_mm: Radial distance from disk center (mm). Typical: 96.52 mm.
            airgap_mm: Distance from top of magnet surface to sensor (mm). Typical: 2-6 mm.
            z_magnet_thickness_mm: Magnet thickness (mm). Used to compute absolute z height.
        """
        self.radius_mm = radius_mm
        self.airgap_mm = airgap_mm
        self.z_mm = z_magnet_thickness_mm + airgap_mm
        
    def position_at_theta_deg(self, theta_deg: float) -> np.ndarray:
        """Get sensor position in 3D space at rotation angle theta.
        
        Sensor is fixed in lab frame; disk rotates beneath it.
        We express sensor position in a frame where disk angle theta is 0,
        so sensor stays at theta=0 in lab frame.
        
        Args:
            theta_deg: Unused (sensor is fixed), kept for API consistency.
            
        Returns:
            [x, y, z] position in mm (Cartesian coordinates, origin at disk center).
        """
        # Sensor is always at theta=0 in lab frame (fixed to stator)
        x = self.radius_mm
        y = 0.0
        z = self.z_mm
        return np.array([x, y, z])
    
    def position_in_meters(self, theta_deg: float = 0.0) -> np.ndarray:
        """Get sensor position in meters (SI units).
        
        Args:
            theta_deg: Unused (sensor is fixed), kept for API consistency.
            
        Returns:
            [x, y, z] position in meters.
        """
        return self.position_at_theta_deg(theta_deg) / 1000.0
    
    def __repr__(self) -> str:
        return f"Sensor(r={self.radius_mm:.2f}mm, airgap={self.airgap_mm:.2f}mm, z={self.z_mm:.2f}mm)"
