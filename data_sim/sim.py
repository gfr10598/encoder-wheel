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

    def __init__(self, sample_rate_hz: int = 5000, noise_rms_lsb: float = 0.8) -> None:
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
# 2b. VELOCITY-BASED DELTA PREDICTOR with Adaptive Learning
# ==============================================================================
class VelocityPredictor:
    """
    Predicts the next delta (velocity) using exponential moving average of past deltas.
    Much simpler and more effective than position matrix for smooth periodic motions.
    """

    def __init__(self, alpha: float = 0.25) -> None:
        """
        alpha: learning rate for exponential moving average (0-1).
        Higher = more responsive to recent changes.
        """
        self.alpha = alpha
        self.predicted_dx: float = 0.0
        self.predicted_dy: float = 0.0

    def predict(self) -> Tuple[int, int]:
        """Return current velocity predictions."""
        return int(round(self.predicted_dx)), int(round(self.predicted_dy))

    def update(self, dx: int, dy: int) -> None:
        """Update velocity prediction based on actual delta."""
        self.predicted_dx = self.alpha * dx + (1 - self.alpha) * self.predicted_dx
        self.predicted_dy = self.alpha * dy + (1 - self.alpha) * self.predicted_dy

    def bootstrap(self, deltas_x: list[int], deltas_y: list[int]) -> None:
        """
        Rapidly initialize predictor using median of initial deltas.
        Called during startup with first N samples to establish baseline velocity.
        """
        if len(deltas_x) > 0:
            # Use median to be robust to outliers
            deltas_x_sorted = sorted(deltas_x)
            deltas_y_sorted = sorted(deltas_y)
            mid = len(deltas_x_sorted) // 2

            self.predicted_dx = float(deltas_x_sorted[mid])
            self.predicted_dy = float(deltas_y_sorted[mid])

    def reset(self) -> None:
        """Reset predictions to zero."""
        self.predicted_dx = 0.0
        self.predicted_dy = 0.0


# ==============================================================================
# 2b. VELOCITY-BASED ENCODER (Delta Prediction with 4-bit Residual)
# ==============================================================================
class VelocityEncoder:
    """
    Encoder using velocity prediction with byte-stuffing escape protocol.
    Predicts delta from EMA of past deltas, quantizes residuals to 4 bits per channel.

    Protocol:
      - Residual byte format: [X_residual_4bit | Y_residual_4bit]
        X & Y range: -8 to +7 encoded as 0x0-0xF (4-bit signed)
      - Control frames: 0xF? where low nibble indicates frame type
        * 0xF0 = position sync: 0xF0 + 4-byte position
        * 0xF1 = state sync: 0xF1 + 4-byte position + 24-byte coefficients
      - Escape sequence: 0xFE + literal byte (for any residual byte >= 0xF0)
    """

    @staticmethod
    def encode(
        x_stream: np.ndarray, y_stream: np.ndarray, alpha: float = 0.25
    ) -> bytearray:
        """
        Encode using velocity prediction with rapid startup bootstrapping.
        Protocol: 0xF0 = position sync, 0xFE = escape for literal 0xF? byte
        """
        compressed_bytes = bytearray()
        predictor = VelocityPredictor(alpha=alpha)
        prev_x, prev_y = 0, 0
        samples_encoded = 0
        bootstrap_size = 12  # Collect 12 deltas for rapid startup

        # Diagnostics
        all_residuals_x = []
        all_residuals_y = []

        def emit_sync_frame(x: int, y: int) -> None:
            """Emit position sync: 0xF0 + 4-byte position"""
            compressed_bytes.append(0xF0)
            compressed_bytes.extend(x.to_bytes(2, byteorder="big", signed=True))
            compressed_bytes.extend(y.to_bytes(2, byteorder="big", signed=True))

        def emit_residual_byte(byte: int) -> None:
            """Emit residual byte, escaping any 0xF? as 0xFE 0xF?"""
            if byte >= 0xF0:  # Any byte with high nibble = F
                compressed_bytes.append(0xFE)
                compressed_bytes.append(byte)
            else:
                compressed_bytes.append(byte)

        # Phase 1: Emit initial sync frame and collect bootstrap deltas
        if len(x_stream) > 0:
            cx, cy = int(x_stream[0]), int(y_stream[0])
            emit_sync_frame(cx, cy)
            prev_x, prev_y = cx, cy

            # Collect initial deltas for bootstrapping, emit positions as sync frames
            bootstrap_deltas_x = []
            bootstrap_deltas_y = []

            for i in range(1, min(bootstrap_size + 1, len(x_stream))):
                cx, cy = int(x_stream[i]), int(y_stream[i])
                dx = s16(cx - prev_x)
                dy = s16(cy - prev_y)
                bootstrap_deltas_x.append(dx)
                bootstrap_deltas_y.append(dy)

                # Emit bootstrap positions as sync frames so decoder can mirror bootstrap
                emit_sync_frame(cx, cy)
                prev_x, prev_y = cx, cy

            # Initialize predictor with bootstrap
            if len(bootstrap_deltas_x) > 0:
                predictor.bootstrap(bootstrap_deltas_x, bootstrap_deltas_y)

            # Now encode from the bootstrap point onward
            for i in range(bootstrap_size + 1, len(x_stream)):
                cx, cy = int(x_stream[i]), int(y_stream[i])

                # Actual delta
                dx = s16(cx - prev_x)
                dy = s16(cy - prev_y)

                # Predict delta using bootstrapped predictor
                pred_dx, pred_dy = predictor.predict()

                # Residual (actual - predicted)
                res_x = dx - pred_dx
                res_y = dy - pred_dy

                all_residuals_x.append(res_x)
                all_residuals_y.append(res_y)

                # Clamp residuals to 4-bit signed range [-8, +7]
                res_x_q = max(-8, min(7, res_x))
                res_y_q = max(-8, min(7, res_y))

                # Encode as 4-bit signed nibbles
                nibble_x = res_x_q & 0x0F
                nibble_y = res_y_q & 0x0F

                # Pack: high 4 bits = X, low 4 bits = Y
                residual_byte = (nibble_x << 4) | nibble_y
                emit_residual_byte(residual_byte)

                # Update predictor
                predictor.update(dx, dy)

                prev_x, prev_y = cx, cy
                samples_encoded += 1

                # Emit sync frame periodically or if prediction error is large
                max_error = max(abs(res_x), abs(res_y))
                if max_error > 16 or samples_encoded >= 256:
                    emit_sync_frame(cx, cy)
                    predictor.reset()
                    samples_encoded = 0

        # Print diagnostics
        if len(all_residuals_x) > 0:
            print(f"\n  Residual statistics (velocity):")
            print(
                f"    X: mean={np.mean(all_residuals_x):.2f}, std={np.std(all_residuals_x):.2f}, "
                f"min={np.min(all_residuals_x)}, max={np.max(all_residuals_x)}"
            )
            print(
                f"    Y: mean={np.mean(all_residuals_y):.2f}, std={np.std(all_residuals_y):.2f}, "
                f"min={np.min(all_residuals_y)}, max={np.max(all_residuals_y)}"
            )

        return compressed_bytes


# ==============================================================================
# 2c. VELOCITY-BASED DECODER
# ==============================================================================
class VelocityDecoder:
    @staticmethod
    def decode(
        byte_stream: bytearray, alpha: float = 0.25
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Decode stream using same velocity predictor as encoder.
        Protocol: 0xF0 = position sync, 0xFE = escape for literal 0xF? byte
        Nibble meanings (4-bit signed residuals):
          0x0 = -8, 0x1 = -7, ..., 0x7 = -1, 0x8 = 0, 0x9 = +1, ..., 0xF = +7
        """
        predictor = VelocityPredictor(alpha=alpha)
        recon_x, recon_y = [], []
        prev_x, prev_y = 0, 0
        ptr = 0
        stream_len = len(byte_stream)

        def read_sync_frame() -> Tuple[bool, int, int]:
            """Try to read position sync (0xF0 + 4-byte position).
            Returns (is_sync, x, y) or (False, 0, 0) if not a sync.
            """
            nonlocal ptr
            if ptr + 4 <= stream_len and byte_stream[ptr] == 0xF0:
                x = int.from_bytes(
                    byte_stream[ptr + 1 : ptr + 3], byteorder="big", signed=True
                )
                y = int.from_bytes(
                    byte_stream[ptr + 3 : ptr + 5], byteorder="big", signed=True
                )
                ptr += 5
                return True, x, y
            return False, 0, 0

        def read_data_byte() -> Tuple[bool, int]:
            """Read next data byte, handling escapes (0xFE 0xF? -> 0xF?).
            Returns (is_valid, byte_value).
            """
            nonlocal ptr
            if ptr >= stream_len:
                return False, 0
            byte = byte_stream[ptr]
            if byte == 0xFE:
                if ptr + 1 < stream_len:
                    escaped_byte = byte_stream[ptr + 1]
                    ptr += 2
                    return True, escaped_byte  # Literal 0xF? byte
                else:
                    return False, 0
            elif byte < 0xF0:
                # Normal data byte (residual)
                ptr += 1
                return True, byte
            else:
                # Unescaped 0xF? (could be control frame), don't consume
                return False, 0

        # Phase 1: Read initial sync frame
        is_sync, cx, cy = read_sync_frame()
        if is_sync:
            recon_x.append(cx)
            recon_y.append(cy)
            prev_x, prev_y = cx, cy

        # Phase 2: Read bootstrap sync frames and collect deltas
        bootstrap_deltas_x = []
        bootstrap_deltas_y = []
        bootstrap_size = 12

        for _ in range(bootstrap_size):
            is_sync, cx, cy = read_sync_frame()
            if is_sync:
                dx = s16(cx - prev_x)
                dy = s16(cy - prev_y)
                bootstrap_deltas_x.append(dx)
                bootstrap_deltas_y.append(dy)
                recon_x.append(cx)
                recon_y.append(cy)
                prev_x, prev_y = cx, cy
            else:
                break

        # Initialize predictor with bootstrap deltas
        if len(bootstrap_deltas_x) > 0:
            predictor.bootstrap(bootstrap_deltas_x, bootstrap_deltas_y)

        # Phase 3: Decode residuals
        while ptr < stream_len:
            # Try to read sync frame first
            is_sync, cx, cy = read_sync_frame()
            if is_sync:
                recon_x.append(cx)
                recon_y.append(cy)
                prev_x, prev_y = cx, cy
                predictor.reset()
            else:
                # Try to read data byte
                is_valid, residual_byte = read_data_byte()
                if is_valid:
                    # Decode 4-bit signed nibbles
                    def decode_4bit(val: int) -> int:
                        # Convert 4-bit unsigned to 4-bit signed
                        val = val & 0x0F
                        if val >= 8:
                            return val - 16
                        return val

                    nibble_x = (residual_byte >> 4) & 0x0F
                    nibble_y = residual_byte & 0x0F

                    res_x = decode_4bit(nibble_x)
                    res_y = decode_4bit(nibble_y)

                    # Predict delta
                    pred_dx, pred_dy = predictor.predict()

                    # Reconstruct: actual_delta = prediction + residual
                    dx = s16(pred_dx + res_x)
                    dy = s16(pred_dy + res_y)

                    # Reconstruct position
                    cx = s16(prev_x + dx)
                    cy = s16(prev_y + dy)

                    recon_x.append(cx)
                    recon_y.append(cy)

                    # Update predictor
                    predictor.update(dx, dy)

                    prev_x, prev_y = cx, cy
                else:
                    # Unexpected byte, skip
                    ptr += 1

        return np.array(recon_x, dtype=np.int16), np.array(recon_y, dtype=np.int16)


# ==============================================================================
# 2d. LINEAR MATRIX PREDICTOR (Affine Transformation with RLS Learning)
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

    def bootstrap(self, positions_x: list[int], positions_y: list[int]) -> None:
        """
        Rapidly initialize affine matrix from a sequence of positions.
        Uses least-squares fit to find best rotation/scaling.
        """
        if len(positions_x) < 3:
            return

        # Use first two position pairs to estimate the matrix
        # [x1, x2] = A*[x0] + B*[y0] + E
        # [y1, y2]   C*[x0]   D*[y0]   F
        x0, y0 = positions_x[0], positions_y[0]
        x1, y1 = positions_x[1], positions_y[1]
        x2, y2 = positions_x[2], positions_y[2]

        # Estimate rotation from deltas
        dx01 = x1 - x0
        dy01 = y1 - y0
        dx02 = x2 - x0
        dy02 = y2 - y0

        # Compute norms for normalization
        norm01 = np.sqrt(dx01**2 + dy01**2 + 1e-6)
        norm02 = np.sqrt(dx02**2 + dy02**2 + 1e-6)

        # Normalize
        dx01_n = dx01 / norm01
        dy01_n = dy01 / norm01
        dx02_n = dx02 / norm02
        dy02_n = dy02 / norm02

        # Estimate rotation matrix from normalized vectors
        # For small rotations, the rotation approximately preserves the second vector
        cos_theta = dx01_n * dx02_n + dy01_n * dy02_n
        sin_theta = -dy01_n * dx02_n + dx01_n * dy02_n

        # Clamp to valid range
        cos_theta = max(-1.0, min(1.0, cos_theta))
        sin_theta = max(-1.0, min(1.0, sin_theta))

        # Set matrix to approximate rotation
        scale = norm02 / (norm01 + 1e-6)
        self.A = cos_theta * scale
        self.B = -sin_theta * scale
        self.C = sin_theta * scale
        self.D = cos_theta * scale

        # Set offset to first position
        self.E = float(x0)
        self.F = float(y0)

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
# 2d. LINEAR MATRIX ENCODER (Affine Prediction with 2-bit Residual Quantization)
# ==============================================================================
class LinearMatrixEncoder:
    """
    Encoder using affine matrix predictor with periodic state synchronization.
    Predicts next position, quantizes residuals to 2 bits per channel,
    packs into single 4-bit nibble per sample.
    Emits full predictor state every 100msec for decoder resynchronization.

    Protocol:
      - Residual byte format: [X_residual_2bit | Y_residual_2bit | padding_2bit | padding_2bit]
        X & Y range: -2, -1, 0, +1 encoded as 0x0-0x3 (2-bit signed)
        Upper 2 bits of each nibble are padding (always 0)
      - Control frames: 0xF? where low nibble indicates frame type
        * 0xF0 = position sync: 0xF0 + 4-byte position
        * 0xF1 = state sync: 0xF1 + 4-byte position + 24-byte coefficients (6×4-byte)
      - Escape sequence: 0xFE + literal byte (for any residual byte >= 0xF0)
    """

    @staticmethod
    def encode(x_stream: np.ndarray, y_stream: np.ndarray) -> bytearray:
        """
        Encode using linear matrix prediction with 2-bit residual quantization.
        Residuals quantized to 2-bit signed: -2, -1, 0, +1
        Emits full state packet (0xF1) every ~500 samples (100msec at 5kHz).
        """
        compressed_bytes = bytearray()
        predictor = LinearMatrixPredictor()
        prev_x, prev_y = 0, 0
        samples_encoded = 0
        samples_since_state = 0
        state_interval = 500  # Emit state every 500 samples (~100msec at 5kHz)
        bootstrap_size = 4

        # Diagnostics
        all_residuals_x = []
        all_residuals_y = []

        if len(x_stream) == 0:
            return compressed_bytes

        # Phase 1: Emit initial position sync
        cx, cy = int(x_stream[0]), int(y_stream[0])
        compressed_bytes.append(0xF0)
        compressed_bytes.extend(cx.to_bytes(2, byteorder="big", signed=True))
        compressed_bytes.extend(cy.to_bytes(2, byteorder="big", signed=True))
        prev_x, prev_y = cx, cy

        # Phase 2: Collect bootstrap samples to initialize predictor
        bootstrap_positions_x = [cx]
        bootstrap_positions_y = [cy]

        for i in range(1, min(bootstrap_size + 1, len(x_stream))):
            cx, cy = int(x_stream[i]), int(y_stream[i])
            bootstrap_positions_x.append(cx)
            bootstrap_positions_y.append(cy)
            prev_x, prev_y = cx, cy

        # Initialize predictor from bootstrap samples
        if len(bootstrap_positions_x) >= 4:
            predictor.bootstrap(bootstrap_positions_x, bootstrap_positions_y)

        # Emit first state packet with initialized coefficients
        compressed_bytes.append(0xF1)  # State packet marker
        compressed_bytes.extend(cx.to_bytes(2, byteorder="big", signed=True))
        compressed_bytes.extend(cy.to_bytes(2, byteorder="big", signed=True))
        # Pack 6 floats (A, B, C, D, E, F) as 4-byte values
        for coeff in [
            predictor.A,
            predictor.B,
            predictor.C,
            predictor.D,
            predictor.E,
            predictor.F,
        ]:
            compressed_bytes.extend(
                int(coeff * 1000).to_bytes(4, byteorder="big", signed=True)
            )
        samples_since_state = 0

        # Phase 3: Encode remaining samples
        for i in range(bootstrap_size + 1, len(x_stream)):
            cx, cy = int(x_stream[i]), int(y_stream[i])

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

            # Update predictor
            predictor.update(prev_x, prev_y, cx, cy)

            prev_x, prev_y = cx, cy
            samples_encoded += 1
            samples_since_state += 1

            # Emit full state packet periodically
            if samples_since_state >= state_interval:
                compressed_bytes.append(0xF1)  # State packet marker
                compressed_bytes.extend(cx.to_bytes(2, byteorder="big", signed=True))
                compressed_bytes.extend(cy.to_bytes(2, byteorder="big", signed=True))
                # Pack coefficients as scaled integers (scale by 1000 for precision)
                for coeff in [
                    predictor.A,
                    predictor.B,
                    predictor.C,
                    predictor.D,
                    predictor.E,
                    predictor.F,
                ]:
                    compressed_bytes.extend(
                        int(coeff * 1000).to_bytes(4, byteorder="big", signed=True)
                    )
                samples_since_state = 0

            # Emit position-only sync frame if residual error is too large
            max_error = max(abs(res_x), abs(res_y))
            if max_error > 8:
                compressed_bytes.append(0xF0)
                compressed_bytes.extend(cx.to_bytes(2, byteorder="big", signed=True))
                compressed_bytes.extend(cy.to_bytes(2, byteorder="big", signed=True))
                predictor.reset()
                samples_encoded = 0
                samples_since_state = 0

        # Print diagnostics
        if len(all_residuals_x) > 0:
            print(f"\n  Residual statistics (matrix with state sync):")
            print(
                f"    X: mean={np.mean(all_residuals_x):.2f}, std={np.std(all_residuals_x):.2f}, "
                f"min={np.min(all_residuals_x)}, max={np.max(all_residuals_x)}"
            )
            print(
                f"    Y: mean={np.mean(all_residuals_y):.2f}, std={np.std(all_residuals_y):.2f}, "
                f"min={np.min(all_residuals_y)}, max={np.max(all_residuals_y)}"
            )

        return compressed_bytes


# ==============================================================================
# 2e. LINEAR MATRIX DECODER (Mirror of Encoder with State Sync)
# ==============================================================================
class LinearMatrixDecoder:
    @staticmethod
    def decode(byte_stream: bytearray) -> Tuple[np.ndarray, np.ndarray]:
        """Decode stream using same affine matrix predictor as encoder.
        Protocol: 0xF0 = position sync, 0xF1 = state sync, 0xFE = escape for literal 0xF?
        Nibble meanings (2-bit signed residuals):
          0b00 = -2, 0b01 = -1, 0b10 = 0, 0b11 = +1
        """
        predictor = LinearMatrixPredictor()
        recon_x, recon_y = [], []
        prev_x, prev_y = 0, 0
        ptr = 0
        stream_len = len(byte_stream)

        while ptr < stream_len:
            ctrl_byte = byte_stream[ptr]

            if ctrl_byte == 0xF0:
                # Position-only sync frame: read uncompressed position, reset predictor
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
                ptr += 5

            elif ctrl_byte == 0xF1:
                # Full state packet: read position + all 6 predictor coefficients
                cx = int.from_bytes(
                    byte_stream[ptr + 1 : ptr + 3], byteorder="big", signed=True
                )
                cy = int.from_bytes(
                    byte_stream[ptr + 3 : ptr + 5], byteorder="big", signed=True
                )
                recon_x.append(cx)
                recon_y.append(cy)
                prev_x, prev_y = cx, cy

                # Extract and restore predictor coefficients (scaled by 1000)
                offset = 5
                coeffs = []
                for _ in range(6):
                    coeff_scaled = int.from_bytes(
                        byte_stream[offset : offset + 4], byteorder="big", signed=True
                    )
                    coeffs.append(coeff_scaled / 1000.0)
                    offset += 4

                predictor.A = coeffs[0]
                predictor.B = coeffs[1]
                predictor.C = coeffs[2]
                predictor.D = coeffs[3]
                predictor.E = coeffs[4]
                predictor.F = coeffs[5]

                ptr += 5 + 24  # 5 bytes header + 6*4 bytes coefficients

            elif ctrl_byte == 0xFE:
                # Escape sequence: next byte is a literal 0xF? residual data
                if ptr + 1 < stream_len:
                    data_byte = byte_stream[ptr + 1]
                    ptr += 2

                    # Decode 2-bit residuals
                    def decode_2bit(val: int) -> int:
                        # Map [0, 1, 2, 3] to [-2, -1, 0, +1]
                        return (val & 0x03) - 2

                    nibble_x = (data_byte >> 2) & 0x03
                    nibble_y = data_byte & 0x03

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

                    # Update predictor
                    predictor.update(prev_x, prev_y, cx, cy)

                    prev_x, prev_y = cx, cy
                else:
                    ptr += 1

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

                # Update predictor (always, without warmup - we're bootstrapped)
                predictor.update(prev_x, prev_y, cx, cy)

                prev_x, prev_y = cx, cy
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

    print("\n=== VELOCITY PREDICTION: EMA Delta Forecasting ===")
    print("Encoding with velocity prediction (alpha=0.25)...", end=" ", flush=True)
    encoded_matrix = VelocityEncoder.encode(final_x, final_y, alpha=0.25)
    print(
        f"done ({len(encoded_matrix):,} bytes, {100*len(encoded_matrix)/raw_bytes:.1f}% of raw)"
    )

    print("Decoding velocity stream...", end=" ", flush=True)
    decoded_x_matrix, decoded_y_matrix = VelocityDecoder.decode(
        encoded_matrix, alpha=0.25
    )
    print("done")

    # Verify velocity reconstruction
    print("Verifying velocity reconstruction...", end=" ", flush=True)
    if not (
        np.array_equal(final_x, decoded_x_matrix)
        and np.array_equal(final_y, decoded_y_matrix)
    ):
        # Debug: find first divergence
        print("\n  MISMATCH!")
        for i in range(min(len(final_x), len(decoded_x_matrix))):
            if final_x[i] != decoded_x_matrix[i] or final_y[i] != decoded_y_matrix[i]:
                print(f"  First divergence at index {i}:")
                print(f"    Angle: {angles[i]:.2f}°, Rate: {rates[i]:.4f} rad/s")
                start = max(0, i - 2)
                end = min(len(final_x), i + 5)
                print(
                    f"    Original X[{start}:{end}]: "
                    + ", ".join(str(int(v)) for v in final_x[start:end])
                )
                print(
                    f"    Decoded X[{start}:{end}]:  "
                    + ", ".join(str(int(v)) for v in decoded_x_matrix[start:end])
                )
                print(
                    f"    Original Y[{start}:{end}]: "
                    + ", ".join(str(int(v)) for v in final_y[start:end])
                )
                print(
                    f"    Decoded Y[{start}:{end}]:  "
                    + ", ".join(str(int(v)) for v in decoded_y_matrix[start:end])
                )
                break
        if len(final_x) != len(decoded_x_matrix):
            print(
                f"  Length mismatch: original {len(final_x)}, decoded {len(decoded_x_matrix)}"
            )
        raise AssertionError("Velocity reconstruction mismatch")
    print("OK")

    # Print first 16 sample values
    print("\nFirst 16 velocity-decoded samples:")
    print("  X: " + ", ".join(str(int(v)) for v in decoded_x_matrix[:16]))
    print("  Y: " + ", ".join(str(int(v)) for v in decoded_y_matrix[:16]))

    # Analyze velocity encoding distribution
    print("\nVelocity encoding distribution:")
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
    print(f"Velocity size:  {len(encoded_matrix):,} bytes")
    print(
        f"Improvement:    {improvement:+.1f}% ({len(encoded) - len(encoded_matrix):,} bytes saved)"
    )
    print(
        f"Sync frames baseline:  {sync_count:,} vs velocity: {sync_count_matrix:,} (delta: {sync_count_matrix - sync_count:+d})"
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
