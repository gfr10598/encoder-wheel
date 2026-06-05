from typing import Tuple
import numpy as np
import matplotlib.pyplot as plt
import unittest


# ==============================================================================
# 0. UTILITY: 16-bit signed arithmetic helpers
# ==============================================================================
def s16(val: int | float) -> int:
    """Clamp value to 16-bit signed range [-32768, 32767]."""
    val = int(val)
    if val > 32767:
        val = val - 65536
    elif val < -32768:
        val = val + 65536
    return val


# ==============================================================================
# 1. PHYSICAL PENDULUM SIMULATOR (ZERO-TO-ZERO COUPLING)
# ==============================================================================
class PendulumSimulator:
    """
    Simulates a 1-meter pendulum swinging from rest at 175° down through 0° (bottom)
    and up the other side. On the uphill climb, as it slows to 2.0 rad/sec,
    an impact jolts its velocity up to 2.2 rad/sec before it comes to rest.
    """

    def __init__(self, sample_rate_hz: int = 5000, noise_rms_lsb: float = 1.0) -> None:
        self.fs: int = sample_rate_hz
        self.dt: float = 1.0 / sample_rate_hz
        self.noise_rms: float = noise_rms_lsb
        self.g: float = 9.81
        self.r: float = 1.0

    def generate_data(
        self,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
        # We simulate dynamically until the pendulum comes to rest on the other side
        theta = 165.0 * np.pi / 180.0  # Start position (175 degrees)
        omega = 0.0  # Start from absolute rest

        theta_list = []
        omega_list = []

        impact_triggered = False
        impact_index = -1
        idx = 0

        # Run simulation loop until velocity crosses zero on the recovery climb
        while True:
            # Gravity acceleration: alpha = -(g/r) * sin(theta)
            alpha = -(self.g / self.r) * np.sin(theta)

            omega += alpha * self.dt
            theta += omega * self.dt

            # Condition: Once we swing through bottom (0 rad), omega becomes negative.
            # As we climb up the other side, gravity decelerates omega back toward 0.
            # Trip the impact when velocity passes -2.0 rad/sec going toward 0.
            if not impact_triggered and theta < 0 and omega > -2.0:
                # Instant shock acceleration from -2.0 rad/sec to -2.2 rad/sec
                omega = -2.2
                impact_triggered = True
                impact_index = idx

            theta_list.append(theta)
            omega_list.append(omega)

            # Break check: Stop the simulation when it hits zero velocity at the end of the swing
            if impact_triggered and omega >= 0.0 or np.degrees(theta) < -180.0:
                break

            idx += 1

        theta_arr = np.array(theta_list)
        omega_arr = np.array(omega_list)
        total_samples = len(theta_arr)

        # Simulate magnetic field from 18 pole pair rotary encoder
        # - 18 pole pairs = 18 complete magnetic cycles per 360° rotation
        # - X channel: sin(18*theta) — sine quadrature
        # - Y channel: cos(18*theta) — cosine quadrature (90° ahead of X)
        # - Amplitude: ±2047 (16-bit signed range, scaled from full encoder swing)
        elec_phase = theta_arr * 18
        raw_x = np.round(2047 * np.sin(elec_phase))
        raw_y = np.round(2047 * np.cos(elec_phase))

        # Superimpose the random electronic white noise floor you want to observe
        np.random.seed(42)
        noise_x = np.random.normal(0, self.noise_rms, total_samples)
        noise_y = np.random.normal(0, self.noise_rms, total_samples)

        final_x = np.round(raw_x + noise_x).astype(np.int16)
        final_y = np.round(raw_y + noise_y).astype(np.int16)

        return final_x, final_y, np.degrees(theta_arr), omega_arr, impact_index


# ==============================================================================
# 2. DELTA-DELTA ENCODER
# ==============================================================================
class DeltaDeltaEncoder:
    @staticmethod
    def encode(x_stream: np.ndarray, y_stream: np.ndarray) -> bytearray:
        compressed_bytes = bytearray()
        prev_x, prev_y = 0, 0
        prev_dx, prev_dy = 0, 0

        for i in range(len(x_stream)):
            cx, cy = int(x_stream[i]), int(y_stream[i])

            if i == 0:
                compressed_bytes.append(0xFF)  # Absolute sync frame anchor
                compressed_bytes.extend(cx.to_bytes(2, byteorder="big", signed=True))
                compressed_bytes.extend(cy.to_bytes(2, byteorder="big", signed=True))
                prev_x, prev_y = cx, cy
                prev_dx, prev_dy = 0, 0
                continue

            dx = cx - prev_x
            dy = cy - prev_y
            ddx = dx - prev_dx
            ddy = dy - prev_dy

            if -7 <= ddx <= 6 and -7 <= ddy <= 6:
                nibble_x = int(ddx + 7) & 0x0F
                nibble_y = int(ddy + 7) & 0x0F
                compressed_bytes.append((nibble_x << 4) | nibble_y)
                prev_x, prev_y = cx, cy
                prev_dx, prev_dy = dx, dy
            else:
                # The +2 LSB/sample jump from the impact triggers this exception block
                compressed_bytes.append(0xFF)
                compressed_bytes.extend(cx.to_bytes(2, byteorder="big", signed=True))
                compressed_bytes.extend(cy.to_bytes(2, byteorder="big", signed=True))
                prev_x, prev_y = cx, cy
                prev_dx, prev_dy = 0, 0

        return compressed_bytes


# ==============================================================================
# 2b. LINEAR MATRIX PREDICTOR (Affine Transformation with Adaptive Learning)
# ==============================================================================
class LinearMatrixPredictor:
    """
    Learns an affine transformation matrix [A B; C D] + [E F] offset
    to predict the next (X, Y) position from the previous position.
    Uses exponential smoothing to adapt coefficients over time.
    """

    def __init__(self) -> None:
        # Affine matrix: X_pred = A*X_prev + B*Y_prev + E
        #               Y_pred = C*X_prev + D*Y_prev + F
        self.A: float = 1.0  # Diagonal (rotation/scaling)
        self.B: float = 0.0  # Cross-coupling (rotational component)
        self.C: float = 0.0  # Cross-coupling
        self.D: float = 1.0  # Diagonal
        self.E: float = 0.0  # X offset
        self.F: float = 0.0  # Y offset

        # Tracking for adaptive updates
        self.error_history_x: list[int] = []
        self.error_history_y: list[int] = []
        self.max_history: int = 32

    def predict(self, x_prev: int, y_prev: int) -> Tuple[int, int]:
        """Predict next position using current matrix coefficients."""
        x_pred = self.A * x_prev + self.B * y_prev + self.E
        y_pred = self.C * x_prev + self.D * y_prev + self.F
        return int(round(x_pred)), int(round(y_pred))

    def update(self, x_prev: int, y_prev: int, x_actual: int, y_actual: int) -> None:
        """Adapt matrix coefficients based on prediction error."""
        x_pred, y_pred = self.predict(x_prev, y_prev)
        err_x = x_actual - x_pred
        err_y = y_actual - y_pred

        self.error_history_x.append(err_x)
        self.error_history_y.append(err_y)

        if len(self.error_history_x) > self.max_history:
            self.error_history_x.pop(0)
            self.error_history_y.pop(0)

        # Gentle adaptive adjustment (learning rate 0.001 per step)
        if len(self.error_history_x) >= 8:
            mean_err_x = sum(self.error_history_x) / len(self.error_history_x)
            mean_err_y = sum(self.error_history_y) / len(self.error_history_y)

            alpha = 0.0005
            if abs(x_prev) > 20:
                self.A += alpha * mean_err_x / x_prev
                self.C += alpha * mean_err_y / x_prev
            if abs(y_prev) > 20:
                self.B += alpha * mean_err_x / y_prev
                self.D += alpha * mean_err_y / y_prev

            self.E += alpha * mean_err_x * 0.5
            self.F += alpha * mean_err_y * 0.5

    def reset(self) -> None:
        """Reset to identity + zero offset."""
        self.A = 1.0
        self.B = 0.0
        self.C = 0.0
        self.D = 1.0
        self.E = 0.0
        self.F = 0.0
        self.error_history_x = []
        self.error_history_y = []


# ==============================================================================
# 2b. LINEAR MATRIX ENCODER (Affine Prediction with 2-bit Residual Quantization)
# ==============================================================================
class LinearMatrixEncoder:
    """
    Encoder using affine matrix predictor.
    Predicts next position, quantizes residuals to 2 bits per channel,
    packs into single 4-bit nibble per sample.
    """

    @staticmethod
    def encode(x_stream: np.ndarray, y_stream: np.ndarray) -> bytearray:
        """
        Encode using linear matrix prediction with 2-bit residual quantization.
        Residuals quantized to 2-bit signed: -2, -1, 0, +1
        """
        compressed_bytes = bytearray()
        predictor = LinearMatrixPredictor()
        prev_x, prev_y = 0, 0
        samples_encoded = 0
        learning_warmup = 32

        # Diagnostics
        all_residuals_x = []
        all_residuals_y = []

        for i in range(len(x_stream)):
            cx, cy = int(x_stream[i]), int(y_stream[i])

            if i == 0:
                # Sync frame: emit uncompressed position
                compressed_bytes.append(0xFF)
                compressed_bytes.extend(cx.to_bytes(2, byteorder="big", signed=True))
                compressed_bytes.extend(cy.to_bytes(2, byteorder="big", signed=True))
                prev_x, prev_y = cx, cy
                predictor.reset()
                samples_encoded = 0
                continue

            # Predict next position using affine transform
            pred_x, pred_y = predictor.predict(prev_x, prev_y)

            # Compute residuals
            res_x = cx - pred_x
            res_y = cy - pred_y

            all_residuals_x.append(res_x)
            all_residuals_y.append(res_y)

            # Quantize to 2-bit signed: clamp to [-2, -1, 0, +1]
            res_x_q = max(-2, min(1, res_x))
            res_y_q = max(-2, min(1, res_y))

            # Encode 2-bit signed: -2→0b00, -1→0b01, 0→0b10, +1→0b11
            def encode_2bit(val: int) -> int:
                return (val + 2) & 0x03

            nibble_x = encode_2bit(res_x_q)
            nibble_y = encode_2bit(res_y_q)

            # Pack: XXYY (4 bits total, X in high 2 bits, Y in low 2 bits)
            compressed_bytes.append((nibble_x << 2) | nibble_y)

            # Adapt predictor after warmup period
            if samples_encoded >= learning_warmup:
                predictor.update(prev_x, prev_y, cx, cy)

            prev_x, prev_y = cx, cy
            samples_encoded += 1

            # Emit sync frame periodically or if prediction error is large
            max_error = max(abs(res_x), abs(res_y))
            if max_error > 8 or samples_encoded >= 256:
                compressed_bytes.append(0xFF)
                compressed_bytes.extend(cx.to_bytes(2, byteorder="big", signed=True))
                compressed_bytes.extend(cy.to_bytes(2, byteorder="big", signed=True))
                predictor.reset()
                samples_encoded = 0

        # Print diagnostics
        if len(all_residuals_x) > 0:
            print(f"\n  Residual statistics:")
            print(f"    X: mean={np.mean(all_residuals_x):.2f}, std={np.std(all_residuals_x):.2f}, "
                  f"min={np.min(all_residuals_x)}, max={np.max(all_residuals_x)}")
            print(f"    Y: mean={np.mean(all_residuals_y):.2f}, std={np.std(all_residuals_y):.2f}, "
                  f"min={np.min(all_residuals_y)}, max={np.max(all_residuals_y)}")

        return compressed_bytes


# ==============================================================================
# 2c. LINEAR MATRIX DECODER (Mirror of Encoder)
# ==============================================================================
class LinearMatrixDecoder:
    @staticmethod
    def decode(byte_stream: bytearray) -> Tuple[np.ndarray, np.ndarray]:
        """Decode stream using same affine matrix predictor as encoder."""
        compressed_bytes = bytearray()
        predictor = LinearMatrixPredictor()
        recon_x, recon_y = [], []
        prev_x, prev_y = 0, 0
        samples_decoded = 0
        learning_warmup = 32
        ptr = 0
        stream_len = len(byte_stream)

        while ptr < stream_len:
            ctrl_byte = byte_stream[ptr]

            if ctrl_byte == 0xFF:
                # Sync frame: read uncompressed position
                cx = int.from_bytes(
                    byte_stream[ptr + 1 : ptr + 3], byteorder="big", signed=True
                )
                cy = int.from_bytes(
                    byte_stream[ptr + 3 : ptr + 5], byteorder="big", signed=True
                )
                recon_x.append(cx)
                recon_y.append(cy)
                prev_x, prev_y = cx, cy
                predictor.reset()
                samples_decoded = 0
                ptr += 5
            else:
                # Decode 2-bit residuals
                def decode_2bit(val: int) -> int:
                    # Map [0, 1, 2, 3] to [-2, -1, 0, +1]
                    return (val & 0x03) - 2

                nibble_x = (ctrl_byte >> 2) & 0x03
                nibble_y = ctrl_byte & 0x03

                res_x_q = decode_2bit(nibble_x)
                res_y_q = decode_2bit(nibble_y)

                # Predict next position
                pred_x, pred_y = predictor.predict(prev_x, prev_y)

                # Reconstruct: actual = prediction + residual
                cx = pred_x + res_x_q
                cy = pred_y + res_y_q

                # Clamp to 16-bit signed range
                cx = s16(cx)
                cy = s16(cy)

                recon_x.append(cx)
                recon_y.append(cy)

                # Adapt predictor after warmup
                if samples_decoded >= learning_warmup:
                    predictor.update(prev_x, prev_y, cx, cy)

                prev_x, prev_y = cx, cy
                samples_decoded += 1
                ptr += 1

        return np.array(recon_x, dtype=np.int16), np.array(recon_y, dtype=np.int16)


# 3. STREAM DECODER
# ==============================================================================
class DeltaDeltaDecoder:
    @staticmethod
    def decode(byte_stream: bytearray) -> Tuple[np.ndarray, np.ndarray]:
        recon_x, recon_y = [], []
        prev_x, prev_y = 0, 0
        prev_dx, prev_dy = 0, 0
        ptr = 0
        stream_len = len(byte_stream)

        while ptr < stream_len:
            ctrl_byte = byte_stream[ptr]
            if ctrl_byte == 0xFF:
                cx = int.from_bytes(
                    byte_stream[ptr + 1 : ptr + 3], byteorder="big", signed=True
                )
                cy = int.from_bytes(
                    byte_stream[ptr + 3 : ptr + 5], byteorder="big", signed=True
                )
                recon_x.append(cx)
                recon_y.append(cy)
                prev_x, prev_y = cx, cy
                prev_dx, prev_dy = 0, 0
                ptr += 5
            else:
                ddx = ((ctrl_byte >> 4) & 0x0F) - 7
                ddy = (ctrl_byte & 0x0F) - 7
                dx = prev_dx + ddx
                dy = prev_dy + ddy
                cx = prev_x + dx
                cy = prev_y + dy
                recon_x.append(cx)
                recon_y.append(cy)
                prev_x, prev_y = cx, cy
                prev_dx, prev_dy = dx, dy
                ptr += 1

        return np.array(recon_x, dtype=np.int16), np.array(recon_y, dtype=np.int16)


# ==============================================================================
# 3b. FILTERED STREAM DECODER (with rate predictor)
# ==============================================================================
class FilteredDeltaDeltaDecoder:
    @staticmethod
    def decode(
        byte_stream: bytearray, alpha_num: int = 1, alpha_den: int = 10
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Decode stream with low-pass filtered rate predictor."""
        recon_x, recon_y = [], []
        prev_x, prev_y = 0, 0
        prev_res_dx, prev_res_dy = 0, 0
        filtered_dx, filtered_dy = 0, 0  # Integer state
        ptr = 0
        stream_len = len(byte_stream)

        while ptr < stream_len:
            ctrl_byte = byte_stream[ptr]
            if ctrl_byte == 0xFF:
                cx = int.from_bytes(
                    byte_stream[ptr + 1 : ptr + 3], byteorder="big", signed=True
                )
                cy = int.from_bytes(
                    byte_stream[ptr + 3 : ptr + 5], byteorder="big", signed=True
                )
                recon_x.append(cx)
                recon_y.append(cy)
                dx = s16(cx - prev_x)
                dy = s16(cy - prev_y)
                prev_x, prev_y = cx, cy
                prev_res_dx, prev_res_dy = 0, 0
                # Reset filter on sync frame to match encoder state
                filtered_dx, filtered_dy = dx, dy
                ptr += 5
            else:
                ddx = ((ctrl_byte >> 4) & 0x0F) - 7
                ddy = (ctrl_byte & 0x0F) - 7
                res_dx = prev_res_dx + ddx
                res_dy = prev_res_dy + ddy

                # Reconstruct delta from residual and prediction
                dx = s16(res_dx + filtered_dx)
                dy = s16(res_dy + filtered_dy)

                cx = s16(prev_x + dx)
                cy = s16(prev_y + dy)
                recon_x.append(cx)
                recon_y.append(cy)

                # Update filter with reconstructed delta
                filtered_dx = s16(
                    (alpha_num * dx + (alpha_den - alpha_num) * filtered_dx)
                    // alpha_den
                )
                filtered_dy = s16(
                    (alpha_num * dy + (alpha_den - alpha_num) * filtered_dy)
                    // alpha_den
                )

                prev_x, prev_y = cx, cy
                prev_res_dx, prev_res_dy = res_dx, res_dy
                ptr += 1

# ==============================================================================
# 4. ANALYSIS AND VISUALIZATION
# ==============================================================================
def analyze_encoding_histogram(
    encoded_bytes: bytearray, plot: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    """Analyze and visualize byte value distribution."""
    delta_bytes = np.array([b for b in encoded_bytes if b != 0xFF])
    delta_unique, delta_counts = np.unique(delta_bytes, return_counts=True)

    # Show histogram stats
    print(f"\n  Total delta-delta bytes: {len(delta_bytes)}")
    print(f"  Unique byte values: {len(delta_unique)}")
    print(
        f"  Entropy (bits): {-sum((delta_counts/len(delta_bytes)) * np.log2(delta_counts/len(delta_bytes) + 1e-10)):.2f}"
    )

    if plot:
        # Create histogram visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4))

        # Full histogram
        ax1.bar(
            delta_unique, delta_counts, color="steelblue", edgecolor="black", alpha=0.7
        )
        ax1.set_xlabel("Byte Value")
        ax1.set_ylabel("Count")
        ax1.set_title("Full Delta-Delta Byte Value Distribution")
        ax1.grid(True, alpha=0.3)

        # Log-scale histogram for better visibility
        ax2.bar(delta_unique, delta_counts, color="coral", edgecolor="black", alpha=0.7)
        ax2.set_yscale("log")
        ax2.set_xlabel("Byte Value")
        ax2.set_ylabel("Count (log scale)")
        ax2.set_title("Delta-Delta Byte Distribution (Log Scale)")
        ax2.grid(True, alpha=0.3, which="both")

        plt.tight_layout()
        plt.show()

    return delta_unique, delta_counts


# ==============================================================================
# 5. PLOTTING AND EVALUATION RUNNER
# ==============================================================================
def run_simulation_and_plot(plot: bool = True) -> None:
    sim = PendulumSimulator(sample_rate_hz=5000, noise_rms_lsb=1.2)
    print("Simulating pendulum swing...", end=" ", flush=True)
    final_x, final_y, angles, rates, impact_idx = sim.generate_data()
    print(f"done ({len(final_x):,} samples, impact at index {impact_idx:,})")

    print("\n=== BASELINE: Delta-Delta Encoding ===")
    print("Encoding with delta-delta compression...", end=" ", flush=True)
    encoded = DeltaDeltaEncoder.encode(final_x, final_y)
    raw_bytes = len(final_x) * 4  # 2 channels × 2 bytes each
    print(f"done ({len(encoded):,} bytes, {100*len(encoded)/raw_bytes:.1f}% of raw)")

    print("Decoding stream...", end=" ", flush=True)
    decoded_x, decoded_y = DeltaDeltaDecoder.decode(encoded)
    print("done")

    # Verify exact data matching
    print("Verifying lossless reconstruction...", end=" ", flush=True)
    assert np.array_equal(final_x, decoded_x) and np.array_equal(final_y, decoded_y)
    print("OK")

    # Print first 16 sample values
    print("\nFirst 16 decoded samples:")
    print("  X: " + ", ".join(str(int(v)) for v in decoded_x[:16]))
    print("  Y: " + ", ".join(str(int(v)) for v in decoded_y[:16]))

    # Analyze baseline encoding distribution
    print("\nBaseline encoding distribution:")
    unique, counts = np.unique(encoded, return_counts=True)
    sync_count = counts[unique == 0xFF][0] if 0xFF in unique else 0
    delta_count = len(encoded) - sync_count
    print(f"  Sync frames (0xFF): {sync_count} ({100*sync_count/len(encoded):.1f}%)")
    print(f"  Delta-delta bytes:  {delta_count} ({100*delta_count/len(encoded):.1f}%)")
    delta_unique, delta_counts = analyze_encoding_histogram(encoded, plot=plot)

    print("\n=== LINEAR MATRIX: Affine Transform Prediction ===")
    print("Encoding with linear matrix prediction (2-bit residuals)...", end=" ", flush=True)
    encoded_matrix = LinearMatrixEncoder.encode(final_x, final_y)
    print(
        f"done ({len(encoded_matrix):,} bytes, {100*len(encoded_matrix)/raw_bytes:.1f}% of raw)"
    )

    print("Decoding matrix stream...", end=" ", flush=True)
    decoded_x_matrix, decoded_y_matrix = LinearMatrixDecoder.decode(encoded_matrix)
    print("done")

    # Verify matrix reconstruction
    print("Verifying matrix reconstruction...", end=" ", flush=True)
    assert np.array_equal(final_x, decoded_x_matrix) and np.array_equal(
        final_y, decoded_y_matrix
    )
    print("OK")

    # Print first 16 sample values
    print("\nFirst 16 matrix-decoded samples:")
    print("  X: " + ", ".join(str(int(v)) for v in decoded_x_matrix[:16]))
    print("  Y: " + ", ".join(str(int(v)) for v in decoded_y_matrix[:16]))

    # Analyze matrix encoding distribution
    print("\nMatrix encoding distribution:")
    unique_matrix, counts_matrix = np.unique(encoded_matrix, return_counts=True)
    sync_count_matrix = (
        counts_matrix[unique_matrix == 0xFF][0] if 0xFF in unique_matrix else 0
    )
    delta_count_matrix = len(encoded_matrix) - sync_count_matrix
    print(
        f"  Sync frames (0xFF): {sync_count_matrix} ({100*sync_count_matrix/len(encoded_matrix):.1f}%)"
    )
    print(
        f"  Residual bytes:     {delta_count_matrix} ({100*delta_count_matrix/len(encoded_matrix):.1f}%)"
    )
    analyze_encoding_histogram(encoded_matrix, plot=plot)

    # Efficiency comparison
    print("\n=== EFFICIENCY COMPARISON ===")
    improvement = (len(encoded) - len(encoded_matrix)) / len(encoded) * 100
    print(f"Baseline size:  {len(encoded):,} bytes")
    print(f"Matrix size:    {len(encoded_matrix):,} bytes")
    print(
        f"Improvement:    {improvement:+.1f}% ({len(encoded) - len(encoded_matrix):,} bytes saved)"
    )
    print(
        f"Sync frames baseline:  {sync_count:,} vs matrix: {sync_count_matrix:,} (delta: {sync_count_matrix - sync_count:+d})"
    )

    # We invert velocity values in the plot to show standard left-to-right positive motion
    display_rates = -rates

    if plot:
        print("\nPlotting trajectory...")
        plt.figure(figsize=(10, 5))
        plt.plot(
            angles[:impact_idx],
            display_rates[:impact_idx],
            color="blue",
            linewidth=2,
            label="Natural Gravity Swing",
        )
        plt.plot(
            angles[impact_idx:],
            display_rates[impact_idx:],
            color="red",
            linewidth=2,
            linestyle="--",
            label="Post-Impact Powered Climb",
        )

        if impact_idx != -1:
            plt.scatter(
                [angles[impact_idx]],
                [display_rates[impact_idx]],
                color="black",
                s=50,
                zorder=5,
                label=f"Jolt Event ({display_rates[impact_idx]:.1f} rad/s at {angles[impact_idx]:.1f}°)",
            )

        plt.title("Inverted Pendulum State Space Profile (Zero-to-Zero)")
        plt.xlabel("Mechanical Angle (Degrees, 0° = Bottom Dead Center)")
        plt.ylabel("Angular Velocity (rad/sec)")
        plt.grid(True, linestyle=":", alpha=0.6)
        plt.legend()
        plt.tight_layout()
        plt.show()
    else:
        print("\nSkipped trajectory plot (use without --no-plot flag to display)")


if __name__ == "__main__":
    import sys

    plot_enabled = "--no-plot" not in sys.argv
    run_simulation_and_plot(plot=plot_enabled)
