#!/usr/bin/env python3
"""
Common geometry calculations for encoder-wheel designs.

Coordinate conventions
----------------------
The wheel lies in the XY plane with its rotation axis along Z.

For each magnet *i* (0-indexed), the magnet is centred on the radial line at
angle  θ_i = i × (2π / N).  In the *local* frame of that magnet:

  • Y-axis  →  radial direction (pointing away from the centre)
  • X-axis  →  tangential direction (CCW positive)
  • Z-axis  →  axial direction (same as wheel axis)

Magnet dimensions
-----------------
  magnet_length     – radial extent    (default 20 mm)
  magnet_width      – tangential extent (default  5 mm)
  magnet_thickness  – axial extent      (default  2 mm)

Inner-corners-touching condition
---------------------------------
When adjacent magnets' inner corners meet exactly, the gap between them at
the inner radius is zero and the inner rim becomes structurally detached from
the outer ring.  The required minimum inner radius is:

    r_inner_min = (magnet_width / 2) / tan(π / N)

This formula can be derived by requiring that the inner-right corner of
magnet i and the inner-left corner of magnet i+1 are the same Cartesian
point.
"""

import math


def min_inner_radius(n_magnets: int, magnet_width: float) -> float:
    """Return the minimum inner radius (mm) at which adjacent inner corners touch.

    Parameters
    ----------
    n_magnets : int
        Total number of magnets (multiple of 12 recommended).
    magnet_width : float
        Tangential width of each magnet (mm).
    """
    if n_magnets < 2:
        raise ValueError("n_magnets must be >= 2")
    return (magnet_width / 2.0) / math.tan(math.pi / n_magnets)


def encoder_geometry(
    n_magnets: int = 12,
    magnet_length: float = 20.0,
    magnet_width: float = 5.0,
    magnet_thickness: float = 2.0,
    inner_radius: float = None,
) -> dict:
    """Compute all geometric parameters for an encoder wheel.

    Parameters
    ----------
    n_magnets : int
        Number of magnets (multiple of 12 recommended for pole-pair symmetry).
    magnet_length : float
        Radial length of each magnet (mm).  Default 20.
    magnet_width : float
        Tangential width of each magnet (mm).  Default 5.
    magnet_thickness : float
        Axial thickness of each magnet (mm).  Default 2.
    inner_radius : float, optional
        Inner radius of the magnet arrangement (mm).
        Defaults to the minimum possible value (inner corners just touching).

    Returns
    -------
    dict
        All geometry parameters needed by the generator scripts.
    """
    r_min = min_inner_radius(n_magnets, magnet_width)

    if inner_radius is None:
        inner_radius = r_min
    elif inner_radius < r_min - 1e-9:
        raise ValueError(
            f"inner_radius={inner_radius:.3f} mm is less than the minimum "
            f"{r_min:.3f} mm for {n_magnets} magnets of width {magnet_width} mm."
        )

    outer_radius = inner_radius + magnet_length
    angle_step = 2.0 * math.pi / n_magnets

    return {
        "n_magnets": n_magnets,
        "magnet_length": magnet_length,
        "magnet_width": magnet_width,
        "magnet_thickness": magnet_thickness,
        "inner_radius": inner_radius,
        "outer_radius": outer_radius,
        "min_inner_radius": r_min,
        "angle_step": angle_step,
        "angle_step_deg": math.degrees(angle_step),
    }


def magnet_corners(geo: dict, index: int) -> list:
    """Return the four XY corners of magnet *index* (top-view, CCW order).

    Corner order
    ------------
    0 : inner corner in the CCW direction
    1 : inner corner in the CW  direction   ← touches corner 0 of magnet index+1
    2 : outer corner in the CW  direction
    3 : outer corner in the CCW direction

    Parameters
    ----------
    geo : dict
        Geometry dictionary from :func:`encoder_geometry`.
    index : int
        Zero-based magnet index (0 .. n_magnets-1).

    Returns
    -------
    list of (float, float)
    """
    angle = index * geo["angle_step"]
    ir = geo["inner_radius"]
    or_ = geo["outer_radius"]
    hw = geo["magnet_width"] / 2.0

    def to_xy(r, t):
        """Local (radial r, tangential t) → global Cartesian (x, y)."""
        return (
            r * math.cos(angle) - t * math.sin(angle),
            r * math.sin(angle) + t * math.cos(angle),
        )

    return [
        to_xy(ir, -hw),   # inner-CCW
        to_xy(ir,  hw),   # inner-CW
        to_xy(or_,  hw),  # outer-CW
        to_xy(or_, -hw),  # outer-CCW
    ]


def all_magnet_corners(geo: dict) -> list:
    """Return corners for every magnet as a list of lists."""
    return [magnet_corners(geo, i) for i in range(geo["n_magnets"])]


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    geo = encoder_geometry(n_magnets=n)
    print(f"Encoder wheel — {n} magnets, 20×5×2 mm")
    print(f"  min inner radius : {geo['min_inner_radius']:.3f} mm")
    print(f"  inner radius     : {geo['inner_radius']:.3f} mm")
    print(f"  outer radius     : {geo['outer_radius']:.3f} mm")
    print(f"  angle step       : {geo['angle_step_deg']:.3f}°")
