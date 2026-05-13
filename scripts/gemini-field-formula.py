import numpy as np

def compute_magnetic_field_mm(pos, dims, Ms):
    """
    Computes the 3D magnetic flux density vector B at an arbitrary position.
    
    Parameters:
    -----------
    pos  : tuple, list, or np.ndarray
           Observation point (x, y, z) in millimeters [mm] 
           relative to the center of the magnet.
    dims : tuple, list, or np.ndarray
           Half-edge dimensions of the prism (a, b, c) in millimeters [mm].
           The full side lengths of the magnet are 2a x 2b x 2c.
    Ms   : float
           Saturation magnetization (or remanence Br) in Tesla [T].
           The magnet is assumed uniformly magnetized along the +z axis.
           
    Returns:
    --------
    B    : np.ndarray
           The magnetic flux density vector [Bx, By, Bz] in Tesla [T].
    """
    x, y, z = np.array(pos, dtype=float)
    a, b, c = np.array(dims, dtype=float)
    
    # Coordinates of the observation point relative to the 8 boundary planes
    X = np.array([x - a, x + a])
    Y = np.array([y - b, y + b])
    Z = np.array([z - c, z + c])
    
    Bx, By, Bz = 0.0, 0.0, 0.0
    prefactor = Ms / (4.0 * np.pi)
    
    # Loop over the 8 vertices of the rectangular prism
    for k in range(2):
        sign_k = (-1) ** (k + 1)
        X_k = X[k]
        
        for m in range(2):
            sign_m = (-1) ** (m + 1)
            Y_m = Y[m]
            
            for n in range(2):
                sign_n = (-1) ** (n + 1)
                Z_n = Z[n]
                
                # Evaluation sign for the current vertex
                sgn = sign_k * sign_m * sign_n
                
                # Distance from the point to the current vertex
                R = np.sqrt(X_k**2 + Y_m**2 + Z_n**2)
                
                # Guard against exact zero divisions at boundaries
                if R == 0:
                    R = 1e-15
                
                # --- Bz Component ---
                num_z = X_k * Y_m
                den_z = Z_n * R
                if abs(den_z) > 1e-15:
                    Bz += sgn * np.arctan(num_z / den_z)
                else:
                    Bz += sgn * np.sign(num_z) * (np.pi / 2.0 if den_z == 0 else 0)
                
                # --- Bx and By Components ---
                # Guard log inputs against values <= 0
                Bx += sgn * np.log(max(R + Y_m, 1e-15))
                By += sgn * np.log(max(R + X_k, 1e-15))
                
    return prefactor * np.array([-Bx, -By, Bz])

# ==========================================================
# Example Usage: Standard Millimeter Block Magnet
# ==========================================================
if __name__ == "__main__":
    # A block magnet with dimensions 40mm x 20mm x 10mm
    half_a = 20.0  # Full width X = 40 mm
    half_b = 10.0  # Full length Y = 20 mm
    half_c = 5.0   # Full thickness Z = 10 mm
    
    # N42 Neodymium remanence (~1.3 Tesla)
    Br = 1.3  
    
    # Measure the field exactly 2.5 mm directly above the top face center
    obs_pt = [0.0, 0.0, half_c + 2.5]  # Z = 7.5 mm
    magnet_dims = [half_a, half_b, half_c]
    
    B_out = compute_magnetic_field_mm(obs_pt, magnet_dims, Br)
    
    print(f"Magnet size:  {2*half_a}mm x {2*half_b}mm x {2*half_c}mm")
    print(f"Sensor Point: x={obs_pt[0]}mm, y={obs_pt[1]}mm, z={obs_pt[2]}mm")
    print(f"B-Field Vector: Bx={B_out[0]:.4f} T, By={B_out[1]:.4f} T, Bz={B_out[2]:.4f} T")
