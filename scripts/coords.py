import math
import numpy as np


def cyl_to_cart(r, theta_rad, z):
    """Convert cylindrical (r, theta (rad), z) to Cartesian (x,y,z).

    r in meters, z in meters.
    """
    x = r * math.cos(theta_rad)
    y = r * math.sin(theta_rad)
    return np.array([x, y, z])


def cart_to_cyl(x, y, z):
    r = math.hypot(x, y)
    theta = math.atan2(y, x)
    return r, theta, z
