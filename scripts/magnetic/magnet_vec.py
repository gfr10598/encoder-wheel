#!/usr/bin/env python3
"""
MagnetCornersVec: variant of MagnetCorners that accepts an arbitrary
magnetization direction vector instead of the fixed ±Z convention.

Useful for radially-magnetized arc magnets where each sub-block has its
magnetization pointing along the local radial (X) axis.

Aharoni corner-sum formula for arbitrary magnetization
-------------------------------------------------------
For a uniformly magnetized rectangular prism with half-dimensions (a, b, c)
in local (x, y, z), the demagnetising-field components at relative position
(dx, dy, dz) from the prism centre are:

  X[i] = dx ± a  (i=0,1)
  Y[j] = dy ± b  (j=0,1)
  Z[k] = dz ± c  (k=0,1)
  r_ijk = sqrt(X²+Y²+Z²)
  sgn   = (-1)^(i+j+k)

Three independent corner-sum quantities are needed:

  S_arctan_xy_zr = Σ sgn * arctan2(X*Y, Z*r)   (arctan with M along Z)
  S_arctan_yz_xr = Σ sgn * arctan2(Y*Z, X*r)   (arctan with M along X)
  S_arctan_xz_yr = Σ sgn * arctan2(X*Z, Y*r)   (arctan with M along Y)
  S_log_xpr      = Σ sgn * log(X + r)
  S_log_ypr      = Σ sgn * log(Y + r)
  S_log_zpr      = Σ sgn * log(Z + r)

Field contribution matrix (each term scaled by M_component / (4π)):

           Mx               My               Mz
  Bx :  +S_arctan_yz_xr   -S_log_zpr      -S_log_ypr
  By :  -S_log_zpr         +S_arctan_xz_yr -S_log_xpr
  Bz :  -S_log_ypr         -S_log_xpr      +S_arctan_xy_zr

All field computation is done in the prism's local frame; the result is
rotated back to global coordinates via the magnet's polar angle.
"""

import math
import numpy as np
from magnet_transform import get_magnet_angle, transform_to_magnet_local, transform_to_global


class MagnetCornersVec:
    """Rectangular-prism field calculator with arbitrary magnetization vector.

    Drop-in replacement for MagnetCorners.compute_field_analytic when the
    magnetization direction is not purely ±Z.

    Example — radially magnetized sub-block at global angle theta_deg:
        center_mm  = [r*cos(theta), r*sin(theta), z_center]
        dims_mm    = [radial_span, arc_width, axial_height]
        Br_vec_local = [Br_T, 0, 0]   # magnetization along local-X (radial)
        B = MagnetCornersVec.compute_field_analytic(center_mm, dims_mm,
                                                     sensor_mm, Br_vec_local)
    """

    @staticmethod
    def compute_field_analytic(center_mm, dims_mm, sensor_mm, Br_vec_local):
        """Compute field from a rectangular prism with arbitrary magnetization.

        Args:
            center_mm (array-like): [x, y, z] prism centre in mm (global frame).
            dims_mm (array-like):   [L, W, T] full prism dimensions in mm.
                                    L = radial (local X), W = tangential (local Y),
                                    T = axial  (local Z).
            sensor_mm (array-like): [x, y, z] sensor position in mm (global frame).
            Br_vec_local (array-like): [Mx, My, Mz] remanent flux density vector
                                    expressed in the prism's LOCAL frame (Tesla).
                                    For radially magnetised: [Br_T, 0, 0].
                                    For axially magnetised:  [0, 0, ±Br_T].

        Returns:
            np.ndarray: [Bx, By, Bz] magnetic field in Tesla in the global frame.
        """
        center = np.asarray(center_mm, dtype=float) / 1000.0
        sensor = np.asarray(sensor_mm, dtype=float) / 1000.0
        dims   = np.asarray(dims_mm,   dtype=float) / 1000.0
        Br     = np.asarray(Br_vec_local, dtype=float)   # [Mx, My, Mz] in local frame

        # Rotate sensor displacement into magnet-local frame
        theta      = get_magnet_angle(center_mm)   # polar angle of prism centre
        rel_global = sensor - center
        rel_local  = transform_to_magnet_local(rel_global, theta)
        dx, dy, dz = rel_local

        L, W, T = dims
        a, b, c = L / 2.0, W / 2.0, T / 2.0

        Xv = np.array([dx - a, dx + a])   # X[0], X[1]
        Yv = np.array([dy - b, dy + b])
        Zv = np.array([dz - c, dz + c])

        eps = 1e-12

        # Accumulate the six independent corner sums
        S_arctan_xy_zr = 0.0
        S_arctan_yz_xr = 0.0
        S_arctan_xz_yr = 0.0
        S_log_xpr      = 0.0
        S_log_ypr      = 0.0
        S_log_zpr      = 0.0

        for i in range(2):
            for j in range(2):
                for k in range(2):
                    x = Xv[i]; y = Yv[j]; z = Zv[k]
                    r = math.sqrt(x*x + y*y + z*z)
                    if r < 1e-15:
                        continue
                    sgn = (-1.0) ** (i + j + k)

                    S_arctan_xy_zr += sgn * math.atan2(x * y, z * r + eps)
                    S_arctan_yz_xr += sgn * math.atan2(y * z, x * r + eps)
                    S_arctan_xz_yr += sgn * math.atan2(x * z, y * r + eps)
                    S_log_xpr      += sgn * math.log(max(x + r, eps))
                    S_log_ypr      += sgn * math.log(max(y + r, eps))
                    S_log_zpr      += sgn * math.log(max(z + r, eps))

        scale = 1.0 / (4.0 * math.pi)
        Mx, My, Mz = Br

        # Field in prism-local frame, assembled from the contribution matrix
        Bx_local = scale * ( Mx *  S_arctan_yz_xr
                           + My * -S_log_zpr
                           + Mz * -S_log_ypr )

        By_local = scale * ( Mx * -S_log_zpr
                           + My *  S_arctan_xz_yr
                           + Mz * -S_log_xpr )

        Bz_local = scale * ( Mx * -S_log_ypr
                           + My * -S_log_xpr
                           + Mz *  S_arctan_xy_zr )

        B_local = np.array([Bx_local, By_local, Bz_local])
        return transform_to_global(B_local, theta)
