# Encoder Wheel Compression Analysis

Magnetic encoder simulation and signal compression framework for quadrature encoder signals.

## Overview

This directory contains analysis and implementation of compression algorithms for 18-pole quadrature encoder signals sampled at 5 kHz with Gaussian noise (0.8 LSB RMS).

**Physical Model:**
- 1-meter pendulum swinging through 360° with impact event
- Simulates realistic motion with slowly-varying angular velocity on constrained ellipse
- 18-pole pairs → 18 complete magnetic cycles per rotation
- X channel: sin(18θ), Y channel: cos(18θ), amplitude ±2047 (16-bit signed)

## Key Findings

### Signal Statistics
- **Position (raw):** X, Y ∈ [−2049, +2049], σ ≈ 1455 LSB
- **Velocity (delta):** dx, dy mean ≈ 0, std ≈ 16.6 LSB, range [−48, +47]
- **Acceleration (delta-delta):** ddx, ddy std ≈ 2.2 LSB, range [−8, +8]

### Compression Results

#### 1. **Velocity Predictor (EMA, α=0.25)** — CURRENT BASELINE
- **Residuals:** σ_x ≈ 1.91 LSB, σ_y ≈ 1.91 LSB
- **Encoding:** 4 bits per variable (±8 range fits in signed 4-bit)
- **Total:** 8.16 bits/sample (4-bit packed + 1.14% sync overhead)
- **Compression:** 3.9× vs uncompressed (32 → 8.16 bits/sample)
- **Data reduction:** 74.5%

#### 2. **Quadratic Predictor (pos + vel + accel)**
- **Residuals:** σ_x ≈ 3.07 LSB, σ_y ≈ 3.08 LSB
- **Issue:** Acceleration amplifies noise (1.9 → 3.1 LSB)
- **2-sigma coverage:** 93.2% (worse than velocity)
- **Verdict:** Physics-limited; velocity is superior

#### 3. **Coupled Linear Predictors** (NEW — see `coupled_predictor.ipynb`)
- **Method 2a: Orthogonal Decomposition (v + a/2)**
  - Tangential + centripetal acceleration model
  - No trig functions; operates in linear domain
- **Method 2b: Angular Velocity Predictor** ⭐
  - Extracts instantaneous angular velocity: $\omega = \frac{x \cdot dy - y \cdot dx}{x^2 + y^2}$
  - Predicts velocity rotation via 2×2 small-angle matrix
  - Geometry-aware; exploits ellipse constraint without trig
  - Adapts $\hat{\omega}$ from residuals
- **Method 2c: Joint Coupling Matrix (2×2)**
  - Learns general affine transformation on velocity vector
  - Exploits X-Y correlation in elliptical motion
  - Adaptive learning with history buffer

## Files

### Notebooks
- **`residual_analysis.ipynb`** — Main analysis pipeline
  - Phase-dependent analysis (signed mean/std by velocity magnitude)
  - Quantization and clipping validation
  - Protocol encoder/decoder metrics
  - Velocity, quadratic, and delta-delta predictors
  - 4-bit packed encoding with escape codes
  
- **`coupled_predictor.ipynb`** (NEW) — Coupled predictor exploration
  - Orthogonal decomposition (tangential + centripetal)
  - Joint matrix coupling analysis
  - Side-by-side comparison plots

### Simulation Code
- **`sim.py`** — Reference implementation
  - `PendulumSimulator`: Physical model with noise injection
  - `VelocityPredictor`: EMA-based velocity estimation (current best)
  - `VelocityEncoder` / `VelocityDecoder`: Protocol codecs (0xFE escapes, 4-bit quantization)
  - `LinearMatrixPredictor`: General affine transformation
  - `DeltaDeltaEncoder`: Acceleration-based alternative
  - `s16()`: Signed 16-bit wraparound helper

## Encoding Architecture

### Current: 4-Bit Packed (8.16 bits/sample)

**Standard frame (1 byte per (X, Y) pair):**
```raw
Byte: [X_nibble | Y_nibble]
      [4-bit signed X | 4-bit signed Y]
Range: {−8..+7} × {−8..+7}
Coverage: 100% of velocity residuals
```

**Escape codes (1 marker + extended):**
- Reserved for future multi-frame state or extended dynamic range
- Currently unused (all residuals fit in ±8)

**Sync frames (every 100 msec @ 5 kHz = 500 samples):**
- **0xF0** (Position sync): 1 byte header + 2 bytes per axis = 5 bytes
- **0xF1** (State sync): 1 byte header + 14 bytes payload = 15 bytes
- Overhead: ~1.14% of total bytes

### Metrics
- **Fundamental:** σ_x = σ_y = 1.91 LSB
- **2-sigma coverage:** 95%+ (reliable prediction window)
- **Axis-alignment frequency:** 18.44% (one axis ≈ 0, other large)
- **Correlation (X, Y residuals):** −0.001 (independent)

## Validation

```bash
# Check Python syntax
python -m py_compile scripts/*.py data_sim/sim.py

# Run main analysis
jupyter notebook data_sim/residual_analysis.ipynb

# Run coupled predictor exploration
jupyter notebook data_sim/coupled_predictor.ipynb
```

## Design Decisions

1. **4-bit over tiers:** Simpler than 3-tier protocol; all residuals fit perfectly
2. **Velocity over acceleration:** 1.91 LSB << 3.07 LSB; noise amplification makes acceleration inferior
3. **Independent X, Y encoding:** Correlation ≈ 0; no savings from joint quantization
4. **Int16 arithmetic throughout:** All computations use signed 16-bit (no floating point in critical path)
5. **EMA smoothing (α=0.25):** Balances responsiveness and noise rejection; convergence in ~12 samples

## Next Steps

1. **Evaluate coupled predictors** in `coupled_predictor.ipynb` for potential sub-1.91 LSB residuals
2. **Consider adaptive quantization** if motion changes character (e.g., impact events)
3. **Implement hardware-efficient codec** using 4-bit packed + escape for production
4. **Validate decoder reconstruction error** on full 100+ millisecond traces
