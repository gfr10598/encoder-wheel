#!/usr/bin/env python3
"""
Escape Code Protocol Efficiency Analysis

Determines which escape code scheme minimizes byte overhead by analyzing
residual distributions from the encoder simulations.

Usage:
    python analyze_escape_codes.py
"""

import numpy as np
import matplotlib.pyplot as plt
from sim import PendulumSimulator, VelocityEncoder


def analyze_escape_codes():
    """Compute protocol efficiency metrics for escape code design decision."""

    # Generate simulation data
    print("Generating encoder simulation data...")
    sim = PendulumSimulator(sample_rate_hz=5000, noise_rms_lsb=0.8)
    x_signal, y_signal, theta, omega, impact_idx = sim.generate_data()

    # Encode with velocity predictor to get residuals
    print("Encoding with velocity predictor...")
    encoder = VelocityEncoder()
    compressed = encoder.encode(x_signal, y_signal, alpha=0.25)

    # For analysis, we need to re-compute residuals to capture the distribution
    from sim import VelocityPredictor

    predictor = VelocityPredictor(alpha=0.25)
    prev_x, prev_y = int(x_signal[0]), int(y_signal[0])
    bootstrap_size = 12

    all_residuals_x = []
    all_residuals_y = []

    # Collect bootstrap deltas
    bootstrap_deltas_x = []
    bootstrap_deltas_y = []
    for i in range(1, min(bootstrap_size + 1, len(x_signal))):
        dx = int(x_signal[i]) - prev_x
        dy = int(y_signal[i]) - prev_y
        bootstrap_deltas_x.append(dx)
        bootstrap_deltas_y.append(dy)
        prev_x, prev_y = int(x_signal[i]), int(y_signal[i])

    if len(bootstrap_deltas_x) > 0:
        predictor.bootstrap(bootstrap_deltas_x, bootstrap_deltas_y)

    # Collect residuals after bootstrap
    prev_x, prev_y = int(x_signal[bootstrap_size]), int(y_signal[bootstrap_size])
    for i in range(bootstrap_size + 1, len(x_signal)):
        cx, cy = int(x_signal[i]), int(y_signal[i])

        pred_x, pred_y = predictor.predict()
        res_x = cx - pred_x
        res_y = cy - pred_y

        all_residuals_x.append(res_x)
        all_residuals_y.append(res_y)

        dx = cx - prev_x
        dy = cy - prev_y
        predictor.update(dx, dy)
        prev_x, prev_y = cx, cy

    vel_residuals_x = np.array(all_residuals_x)
    vel_residuals_y = np.array(all_residuals_y)

    # Compute metrics
    print("\n" + "=" * 70)
    print("ESCAPE CODE PROTOCOL DECISION METRICS")
    print("=" * 70)

    # Metric 1: Tier 1 Sufficiency
    tier1_mask = (np.abs(vel_residuals_x) <= 1) & (np.abs(vel_residuals_y) <= 1)
    tier1_pct = 100 * np.mean(tier1_mask)

    # Metric 2: Tier 2 Necessity
    tier2_mask = (
        (np.abs(vel_residuals_x) <= 3) & (np.abs(vel_residuals_y) <= 3) & ~tier1_mask
    )
    tier2_pct = 100 * np.mean(tier2_mask)

    # Metric 3: Axis-alignment frequency
    axis_align_mask = (
        (np.abs(vel_residuals_x) <= 1) & (np.abs(vel_residuals_y) > 2)
    ) | ((np.abs(vel_residuals_y) <= 1) & (np.abs(vel_residuals_x) > 2))
    axis_align_pct = 100 * np.mean(axis_align_mask)

    # Metric 4: Tier 3 Fallback
    tier3_mask = (np.abs(vel_residuals_x) > 3) | (np.abs(vel_residuals_y) > 3)
    tier3_pct = 100 * np.mean(tier3_mask)

    # Metric 5: Joint distribution
    max_x, min_x = np.max(vel_residuals_x), np.min(vel_residuals_x)
    max_y, min_y = np.max(vel_residuals_y), np.min(vel_residuals_y)
    correlation = np.corrcoef(vel_residuals_x, vel_residuals_y)[0, 1]

    print(f"\n1. TIER 1 COVERAGE (Standard {{-1,0,+1}}²):")
    print(
        f"   {tier1_pct:.2f}% of {len(vel_residuals_x)} samples fit in standard 2-bit range"
    )
    print(f"   → Tier 1 dominates: only 1 byte per sample")

    print(f"\n2. TIER 2 DEMAND (Extended {{-2..+3}}²):")
    print(f"   {tier2_pct:.2f}% of samples need tier 2 escape codes")
    print(
        f"   → Estimate: {int(tier2_pct/100 * len(vel_residuals_x))} samples need 2 bytes"
    )

    print(f"\n3. AXIS-ALIGNMENT FREQUENCY:")
    print(f"   {axis_align_pct:.2f}% of samples have one axis ≈0, other axis large")
    if axis_align_pct > 0.3:
        print(f"   → Suggests Option B/C (zero-axis escape 0x9) WORTH IT")
    else:
        print(f"   → Option B/C (zero-axis escape 0x9) NOT WORTH IT")

    print(f"\n4. TIER 3 FALLBACK (Exceed {{-2..+3}}²):")
    print(f"   {tier3_pct:.2f}% of samples exceed extended range")
    print(
        f"   → Estimate: {int(tier3_pct/100 * len(vel_residuals_x))} samples need raw pairs (0xA)"
    )

    print(f"\n5. JOINT DISTRIBUTION:")
    print(f"   X range: [{min_x}, {max_x}]")
    print(f"   Y range: [{min_y}, {max_y}]")
    print(f"   Correlation: {correlation:.3f} (0=independent, ±1=correlated)")
    if abs(correlation) > 0.5:
        print(f"   → Axes are correlated (coupled behavior)")
    else:
        print(f"   → Axes are largely independent")

    # Byte cost estimates
    print("\n" + "=" * 70)
    print("PROTOCOL RECOMMENDATION")
    print("=" * 70)

    avg_bytes_option_a = 1.0 + (tier2_pct / 100 * 1.0) + (tier3_pct / 100 * 2.0)
    print(f"\nOption A (per-axis extended, 3 codes 0x2/0x6/0x8):")
    print(f"  Average bytes per sample: {avg_bytes_option_a:.4f}")
    print(f"  Escape codes used: 0x2, 0x6, 0x8, 0xA (raw), 0xB (sync), 0x9/0xE (spare)")

    if axis_align_pct > 0.3:
        avg_bytes_option_c = (
            1.0
            + (tier2_pct / 100 * 1.0)
            + (axis_align_pct / 100 * 0.5)
            + (tier3_pct / 100 * 2.0)
        )
        print(f"\nOption C (hybrid: per-axis + zero-axis, 4 codes 0x2/0x6/0x8/0x9):")
        print(f"  Average bytes per sample: {avg_bytes_option_c:.4f}")
        print(
            f"  Escape codes used: 0x2, 0x6, 0x8, 0x9 (zero-axis), 0xA (raw), 0xB (sync), 0xE (spare)"
        )
        print(
            f"  Advantage: Saves {(avg_bytes_option_a - avg_bytes_option_c)*len(vel_residuals_x):.0f} bytes total"
        )

    print(f"\nConclusion:")
    if axis_align_pct > 0.3:
        print(f"  → Use Option C (hybrid): per-axis + zero-axis escape mode")
    else:
        print(
            f"  → Use Option A (per-axis only): simpler protocol, negligible byte loss"
        )

    # 2D histogram visualization
    print("\nGenerating 2D residual distribution plot...")
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    h = ax.hist2d(vel_residuals_x, vel_residuals_y, bins=20, cmap="YlOrRd", cmin=1)
    ax.axhline(y=0, color="k", linestyle="-", alpha=0.2, linewidth=0.5)
    ax.axvline(x=0, color="k", linestyle="-", alpha=0.2, linewidth=0.5)
    ax.axhline(y=1, color="b", linestyle="--", alpha=0.3, label="Tier 1 bound (±1)")
    ax.axvline(x=1, color="b", linestyle="--", alpha=0.3)
    ax.axhline(y=-1, color="b", linestyle="--", alpha=0.3)
    ax.axvline(x=-1, color="b", linestyle="--", alpha=0.3)
    ax.axhline(y=3, color="g", linestyle="--", alpha=0.3, label="Tier 2 bound (±3)")
    ax.axvline(x=3, color="g", linestyle="--", alpha=0.3)
    ax.axhline(y=-3, color="g", linestyle="--", alpha=0.3)
    ax.axvline(x=-3, color="g", linestyle="--", alpha=0.3)
    ax.set_xlabel("X Residual", fontsize=12)
    ax.set_ylabel("Y Residual", fontsize=12)
    ax.set_title(
        "Joint Distribution: Velocity Encoder Residuals\n(Blue: Tier 1, Green: Tier 2)",
        fontsize=12,
    )
    ax.legend()
    plt.colorbar(h[3], ax=ax, label="Sample count")
    plt.tight_layout()
    plt.savefig("escape_code_residual_distribution.png", dpi=100)
    print(f"  → Saved to: escape_code_residual_distribution.png")
    plt.close()

    print("\n" + "=" * 70)
    print("Analysis complete.")
    print("=" * 70)


if __name__ == "__main__":
    analyze_escape_codes()
