"""Rotation helpers for magnet-local ↔ global coordinate transforms.

All rotations are in the x-y plane (around the z-axis).  The z-component
is never affected.

Convention: a magnet's *local* x-axis points radially outward from the disk
centre toward the magnet centre.  If the magnet centre is at (cx, cy), the
magnet angle is theta = atan2(cy, cx).

  global → local  : rotate by -theta
  local  → global : rotate by +theta
"""

import math
import numpy as np


def get_magnet_angle(center):
    """Return the angle (radians) of the magnet's radial axis in global coords.

    center: sequence [x, y, z] in any units (only x and y are used).
    Returns 0 for a magnet at the origin.
    """
    cx, cy = float(center[0]), float(center[1])
    return math.atan2(cy, cx)


def _rot2d(vec3, theta):
    """Rotate the x-y components of vec3 by theta radians; z unchanged."""
    c, s = math.cos(theta), math.sin(theta)
    x, y, z = float(vec3[0]), float(vec3[1]), float(vec3[2])
    return np.array([c * x - s * y, s * x + c * y, z])


def transform_to_magnet_local(vec_global, theta):
    """Rotate a vector from global frame to magnet-local frame (rotate by -theta)."""
    return _rot2d(vec_global, -theta)


def transform_to_global(vec_local, theta):
    """Rotate a vector from magnet-local frame to global frame (rotate by +theta)."""
    return _rot2d(vec_local, theta)


# Alias used in analysis_utils for field vectors
transform_vector_to_global = transform_to_global
