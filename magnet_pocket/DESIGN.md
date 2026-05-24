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

```raw
  Bore face (cross-section, looking along +X)

       +------------------------------+
       |       magnet pocket          |
       |                              |
  -----+<- bore_snap_mm ->|           +-----
       |  \ clips over    |           |
       |   \ edge radius  |           |
       +------------------------------+
                          ^
                  edge_radius_other_mm
```

`holder.bore_snap_mm` is the radial inward protrusion of the retention lip.
It must not exceed `magnet.edge_radius_other_mm` — the snap grips by engaging the
curved surface, not by deforming past a hard corner.

The snaps are interleaved between magnet cells. 

---

## Inter-cell comb

The tangential face of each cell carries a comb of `comb.count` teeth.
When two adjacent cells are assembled, their combs interleave along Z: each tooth
from cell A nestles in a gap from cell B, and vice versa.

### Tooth layout

The snaps for each cell are defined within that cell, and interleave with adjacent cells, sharing
identical faces with opposite orientation.
With `N = comb.count` teeth per face and comb spanning the full cell axial height H:

```raw
  tooth pitch   p = H / (2*N)
  tooth width   w = p - comb.axial_gap          (axial, in Z; axial_gap is the design gap between teeth)
  tooth depth   d = comb.thickness_mm           (tangential, in Y)
```

**Left-face tooth centres** (Z positions, from cell origin):

```raw
  Z_L(k) = p * (2*k - 1 - N),   k = 1 ... N
```

**Right-face tooth centres** are the C2 images of the left:

```raw
  Z_R(k) = -Z_L(k)
```

When cell A's right comb (-Z_L) meets cell B's left comb (+Z_L), the two sets
alternate perfectly in Z, filling the axial span with 2*N evenly spaced teeth.

Example with N=3, H=14 mm, p=2.333 mm:

```raw
  Left  teeth at Z (mm):  -4.667,  -0.667,   3.333
  Right teeth at Z (mm):   4.667,   0.667,  -3.333
  Interleaved (sorted):   -4.667,  -3.333,  -0.667,  0.667,  3.333,  4.667  <- alternates L/R
```

### Comb snap overhang

Each tooth tip carries an overhang of `comb.snap_overhang_mm` on its outer edge
(the face that slides behind an adjacent tooth body when assembled).  Snap geometry
on tooth tips follows the same `snap_type` convention as the bore retention snap.

---

## C2 symmetry analysis

### Individual cell

The C2 axis is the radial (+X) direction through the cell's geometric centre
(Y=0, Z=0).  Under this 180-degree rotation: Y -> -Y, Z -> -Z.

| Feature | C2 image | Symmetric? |
|---------|----------|------------|
| Magnet pocket (centred at Y=0, Z=0) | itself | yes |
| Left tangential face | right tangential face | yes |
| Top axial end face | bottom axial end face | yes |
| Left comb teeth {Z_L(k)} | {-Z_L(k)} = right comb teeth | yes |
| Bore retention lip | itself | yes (centred in Y and Z) |

### Full ring

The ring C2 axis is the global Z (ring axis).  Under 180-degree rotation, cell at
angle theta maps to cell at theta+180.  With an **even** `magnet_count`, every cell
has an exact partner diametrically opposite, so the ring is C2-symmetric.

**Requirement**: `magnet_count` must be even.

---

## Config parameters

| Key | Units | Meaning |
|-----|-------|---------|
| `magnet.radial_mm` | mm | Magnet radial dimension (into bore wall) |
| `magnet.tangential_mm` | mm | Magnet tangential dimension (around ring) |
| `magnet.axial_mm` | mm | Magnet axial dimension (along ring axis) |
| `magnet.edge_radius_axial_mm` | mm | Fillet radius on axial (Z-parallel) pocket edges |
| `magnet.edge_radius_other_mm` | mm | Fillet radius on bore-face and outer-face edges |
| `holder.material` | — | Print material (informational) |
| `holder.magnet_count` | — | Total magnets in ring (must be even) |
| `holder.ID_mm` | mm | Inner diameter of assembled ring |
| `holder.thickness_mm` | mm | Radial wall thickness (magnet + outer wall) |
| `holder.end_face_mm` | mm | Axial end-wall thickness (top and bottom) |
| `holder.clearance_mm` | mm | Magnet pocket clearance (total, split equally each side) |
| `holder.bore_snap_mm` | mm | Radial inward protrusion of bore retention lip |
| `comb.count` | — | Teeth per tangential face |
| `comb.thickness_mm` | mm | Tooth depth in tangential (Y) direction |
| `comb.axial_gap` | mm | Design gap between interleaved teeth (sets tooth width) |
| `comb.clearance_mm` | mm | Fit clearance between assembled tangential faces |
| `comb.snap_overhang_mm` | mm | Snap overhang depth at comb tooth tips |
| `comb.snap_type` | — | `full` / `edges` / `corners` |

---

## Validation rules

All rules must pass before geometry generation proceeds.

| ID | Name | Condition | Formula |
|----|------|-----------|---------|
| V1  | Even count | C2 ring symmetry | `magnet_count % 2 == 0` |
| V2  | Radial fit | Magnet + clearance fits inside wall | `magnet.radial_mm + clearance_mm < thickness_mm` |
| V3  | Outer wall printable | Outer wall meets min FDM thickness (0.8 mm) | `thickness_mm - magnet.radial_mm - clearance_mm >= 0.8` |
| V4  | Tangential fit at bore | Magnet + one interleaved comb tooth fit within bore arc | `magnet.tangential_mm + clearance_mm + comb.thickness_mm + comb.clearance_mm <= W_i` |
| V6  | Comb tooth depth | Tooth depth exceeds clearance | `comb.thickness_mm > comb.clearance_mm` |
| V7  | Snap ≤ half tooth | Snap doesn't consume whole tooth | `comb.snap_overhang_mm <= comb.thickness_mm / 2` |
| V8  | Bore snap ≤ edge radius | Snap engages curve, not hard corner | `bore_snap_mm <= magnet.edge_radius_other_mm` |
| V9  | Axial fillet valid | Fillet fits on axial (Z-parallel) pocket edge | `edge_radius_axial_mm <= min(tangential_mm, radial_mm) / 2` |
| V10 | Other fillet valid | Fillet fits on bore-face edge (axial × tangential) | `edge_radius_other_mm <= min(axial_mm, tangential_mm) / 2` |
| V11 | End face positive | End walls have positive thickness | `end_face_mm > 0` |
| V13 | snap_type valid | Recognised snap type | `snap_type in (full, edges, corners)` |
| V14 | Snap deflection clears magnet | Inter-magnet space exceeds snap structure depth | `W_i - magnet.tangential_mm > comb.thickness_mm + comb.snap_overhang_mm + comb.clearance_mm` |
