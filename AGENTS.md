# AGENTS.md

## Repository fundamentals

### Project shape

- This is a **standard-library-only Python generator repository**.
- The shared geometry core lives in `scripts/common.py`.
- Fabrication generators live in:
  - `scripts/generate_laser.py`
  - `scripts/generate_cnc.py`
  - `scripts/generate_3d.py`
- Documentation SVGs are checked in under `images/`.

### Working conventions

- Prefer **small, documentation-first, script-generated** changes over hand-edited
  drawing assets.
- Keep design math explicit in markdown or generator code so future CAD work can
  trace the geometry decisions.
- Avoid adding third-party Python dependencies unless they are clearly required;
  the existing scripts use only the standard library.

### Validation

Use lightweight script validation:

```bash
python -m py_compile scripts/*.py
python scripts/generate_laser.py --output /tmp/encoder_wheel_laser.svg
python scripts/generate_cnc.py --output /tmp/encoder_wheel_cnc.dxf
python scripts/generate_3d.py --output /tmp/encoder_wheel_3d.scad
python scripts/generate_half_ring_docs.py
```

`python -m unittest discover -v` currently reports **no tests** in this clone, so
script execution is the main regression check.

## 10 in Half Ring Over Magnets

This repository now captures the requested **documentation-only** design intent
for the printed half ring that snaps over the steel backing half ring and its
magnet array.  There is still **no CAD implementation** for this part in the
main generators; the current change only records the geometry, math, and SVG
reference diagrams for future agent or CAD work.

### Fixed inputs

| Item | Value |
|------|-------|
| Printed cover half ring | 8.492 in OD, 5.508 in ID |
| Steel backing half ring | 8.000 in OD, 6.000 in ID, 1/8 in thick |
| Magnet size | 20 × 5 × 2 mm |
| Magnet count | 90 total, 45 per half ring |
| Base thickness | 1.0 mm |
| Magnet pocket / end-wall thickness | 2.04 mm |
| Steel capture walls | 1/4 in − 0.1 mm = 6.25 mm |
| Extra wall height above steel cavity | 1.0 mm |
| Snap overhang | 0.2 mm |
| Outer retention tabs | 2.0 mm wide, 1.0 mm radial overhang |

### Derived dimensions used in the diagrams

| Derived item | Value |
|--------------|-------|
| Printed cover inner radius | 69.95 mm |
| Printed cover outer radius | 107.85 mm |
| Cover radial span | 37.90 mm (1.492 in) |
| Steel ring inner radius | 76.20 mm |
| Steel ring outer radius | 101.60 mm |
| Steel ring radial span | 25.40 mm |
| Illustrated magnet inner radius | 78.90 mm |
| Illustrated magnet outer radius | 98.90 mm |
| Magnet shoulder inside steel ring | 2.70 mm each side |
| Radial spare to the 8 in OD | 2.70 mm |

### Top-view wedge math

The half ring carries **45 magnets over 180° / 90 magnets over 360°**.  The
**2.04 mm value belongs to the magnet-pocket/end-wall thickness**, not the wedge
width.  The wedge width is derived from fitting 90 magnets around the full 8 in
OD steel ring:

- Angular pitch = 360° / 90 = **4.00°**
- Outer pitch at the 8 in steel OD = 2π × 101.6 / 90 = **7.09 mm**
- Outer wedge width = 7.09 − 5.00 = **2.09 mm**

That same pitch narrows toward the steel ring ID:

- Inner pitch at the 6 in steel ID = 2π × 76.2 / 90 = **5.32 mm**
- Inner wedge throat = 5.32 − 5.00 = **0.32 mm**

That confirms the requested wedge shape is indeed **“about 0.2 mm”** at the
inner radius while widening to about **2.09 mm** at the outer radius.

### 8 in OD fit constraint

The 20 mm magnets are shown centered on the 1/8 in steel ring:

- steel outer radius = **101.60 mm**
- magnet outer radius = **98.90 mm**
- remaining radial margin to the 8 in OD = **2.70 mm**

That preserves the requested “few mm to spare” inside the 8 in outer diameter.

### Cross-section intent

The cross-section diagrams show the requested stack from the top cover downward:

1. **1.0 mm base skin** across the full 1.492 in radial span
2. **2.04 mm magnet-stop walls** at the inner and outer ends of the 20 mm magnet
3. **6.25 mm steel-capture walls** around the 1/8 in steel ring
4. **1.0 mm extra wall extension** beyond the steel cavity
5. **0.2 mm snap overhang** at the lower edge so the steel half ring snaps in

### Diagram assets

Regenerate the SVG assets with:

```bash
python scripts/generate_half_ring_docs.py
```

#### Cross section

![Half ring cross section](images/half_ring_over_magnets_cross_section.svg)

#### Top view

![Half ring top view](images/half_ring_over_magnets_top_view.svg)

#### Top-side perspective

![Half ring perspective](images/half_ring_over_magnets_perspective.svg)
