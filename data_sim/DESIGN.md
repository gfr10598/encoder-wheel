# 18 Pole-Pair Rotary Encoder: Sync-Framed Base-39 Dual-Axis Tracking Protocol

This protocol specifies an ultra-low-bandwidth, zero-latency streaming compression architecture for an inverted pendulum tracking system utilizing an 18 pole-pair magnetic rotary encoder sampled at 5 kHz.

## 1. System Constants & Parameters
* Sensor Range: 12-bit Peak-to-Peak (Peak vector radius R ≈ 1500 LSB)
* Sensor Noise Floor: σ = 0.8 LSB
* Dynamics: Max rotational velocity ≈ 7 rad/sec (≈ 126 rad/sec electrical)
* Sampling Interval: dt = 200 μs (5 kHz)
* Pole-Pair Multiplier: 18 electrical cycles per mechanical revolution
* Predictor Architecture: Dual 1 kHz single-pole Low-Pass Filters tracking both Angular Velocity (filtered_omega) and Radial Velocity (filtered_dr) to natively absorb uncalibrated ellipse distortions.

---

## 2. Normal Tracking Block (Base-39 Matrix)
Normal data samples are packed into rigid groups of 3 consecutive time steps. Each individual time sample isolates a joint token combining radial and non-linear tangential innovations.

### Innovation Alphabet Sizes
* Radial Component (ε_R): 3 States (-1, 0, +1) - Kept tight via active radial velocity tracking.
* Tangential Component (ε_T): 13 States (0, ±1, ±2, ±3, ±4, ±6, ±9)
* Total Joint Tokens per Sample: 3 × 13 = 39 states (Indices 0 to 38)

### Base-39 Word Combination Math
Three sequential tokens (T₁, T₂, T₃) are compressed into a single 16-bit integer container using base-39 positional multiplication:
Word_Value = ((T_1 * 39) + T_2) * 39 + T_3

* Normal Code Range: 0 to 59,318 (0x0000 to 0xE7B6)
* Transmission Footprint: 2 bytes per 3 samples (5.33 bits per sample pair)
* Byte 0 Constraint: The first byte of any normal data block can only ever range from 0x00 to 0xE7.

---

## 3. Inline Zero-Crossing Sync Frame
The moment the tracking vector executes a cosine channel zero-crossing (crosses the y-axis), the encoder halts normal execution, flushes any partial token combinations, and immediately transmits a 6-byte (48-bit) Zero-Knowledge Sync Block in Big Endian / Network Byte Order.

### 6-Byte Serial Byte Layout
Byte 0: Word 1 High Byte [Ranges from 0xE7 to 0xF7]
Byte 1: Word 1 Low Byte  [Word 1 = 59,320 + Signed 12-bit Sine Value biased by +2048]
Byte 2: Payload Byte     [Upper 5 bits = 0x1A Fingerprint, Lower 3 bits = Coarse Radial Velocity]
Byte 3: Cosine 1 Sample  [8-bit signed int8_t]
Byte 4: Cosine 2 Sample  [8-bit signed int8_t]
Byte 5: Cosine 3 Sample  [8-bit signed int8_t]

---

## 4. Framing Inference and Look-Ahead Byte Sync
When the decoder cold-boots mid-fall or emerges from a violent 10 ms mechanical noise burst, it scans incoming bytes sequentially using a sliding window parser.

Framing alignment is achieved by looking for the explicit signature of the 0x1A Fingerprint:
1. Scan for a byte configuration matching the pattern 11010_xxx (where the upper 5 bits equal 0x1A).
2. Evaluate the 16-bit word located two positions backward in history (Word 1 position).
3. If that backward word sits within the valid sync range of 59,320 to 63,415 (0xE7B8 to 0xF7B7), a valid sync frame match is confirmed.
4. The decoder extracts the 12-bit signed Sine axis, captures the three raw cosine values to calculate the velocity slope, re-seeds both the angular and radial tracking filters, and instantly achieves perfect tracking synchronization within a 2-word look-ahead window.
