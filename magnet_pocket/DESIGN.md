# Magnet Pocket Cell — Design Document

## Overview

A parametric single-magnet holder cell that assembles into a closed ring.
Each cell holds one rectangular NdFeB magnet that slides radially inward through the
bore opening and lies flush with the inner diameter (ID) surface.

Adjacent cells connect along their shared tangential walls via a **comb interlock**:
the wall carries a set of alternating teeth, with odd-indexed teeth belonging to the
left cell and even-indexed teeth belonging to the right cell.  Each tooth tip carries
a snap overhang so the ring self-locks when assembled.

Both the individual cell and the complete ring are required to have **C2 symmetry**
(invariance under 180° rotation about the appropriate axis).

---

## Coordinate system

Cell-local frame, origin at the geometric centre of the cell body:

```raw
         Z (axial, along ring axis)
         |      +Y (tangential, direction of increasing angle)
         |    /
         |  /
         +----------->  +X (radial, outward from ring centre)
```

Ring-global frame: ring axis is global Z; a cell at angle theta has its +X aligned
with the outward radial direction at that angle.

---

## Cell body geometry

Each cell is a trapezoidal-prism wedge (constant angle alpha) before pocketing.

| Quantity | Symbol | Expression | Notes |
|----------|--------|------------|-------|
| Inner radius | R_i | `ID_mm / 2` | flush with bore |
| Outer radius | R_o | `R_i + thickness_mm` | outer surface |
| Angular pitch | alpha | `360 deg / magnet_count` | full-ring pitch |
| Arc width at bore | W_i | `pi * ID_mm / magnet_count` | smallest cross-section |
| Cell axial height | H | `magnet.axial_mm + 2 * end_face_mm` | |

The cell spans +/-alpha/2 about its centre angle.

---

## Magnet pocket and retention snap

### Pocket geometry

The magnet slides **radially inward** through the bore face and comes to rest flush
with the ID surface (inner face of magnet = inner face of cell at R_i).

```raw
  <- radial (X) ->

  R_i              R_i + radial_mm     R_o
   |<---- magnet ----->|<-- outer wall -->|
   |  (flush with bore)|                 |
```

| Feature | Expression |
|---------|------------|
| Pocket inner face | R_i (flush with bore) |
| Pocket depth (radial) | `magnet.radial_mm + clearance_mm` |
| Outer wall thickness | `thickness_mm - magnet.radial_mm - clearance_mm` |
| Pocket tangential width | `magnet.tangential_mm + clearance_mm` |
| Pocket axial height | `magnet.axial_mm + clearance_mm` |

The pocket has five closed faces (outer/top/bottom/left/right) and one open face at
the bore.  Pocket edges are filleted:

- Edges parallel to Z (axial): radius `magnet.edge_radius_axial_mm`
- All other edges: radius `magnet.edge_radius_other_mm`

### Bore-side retention snap

Because the magnet is flush with the bore, the only radially accessible feature is
the **rounded corner** on the inner edge of the magnet.  Retention lips project
slightly inward (-X) from the bore opening, engaging the magnet's
`edge_radius_other_mm` radius as the magnet snaps in.
