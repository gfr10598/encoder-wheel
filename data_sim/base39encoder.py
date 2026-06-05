import struct

RADIUS = 1500
ALPHA_Q15 = 9175
SYNC_BASE_CODE = 59320
SYNC_MAX_CODE = 63415

TANGENT_DICT = [-9, -6, -4, -3, -2, -1, 0, 1, 2, 3, 4, 6, 9]


class Base39Encoder:
    def __init__(self):
        self.cos_state = RADIUS
        self.sin_state = 0
        self.filtered_omega = 0
        self.filtered_dr = 0
        self.token_buffer = []
        self.cos_history = [0, 0, 0]

    def _quantize_radial(self, error):
        if error <= -1:
            return 0
        if error >= 1:
            return 2
        return 1

    def _quantize_tangent(self, error):
        min_dist = float("inf")
        best_idx = 6
        for i, val in enumerate(TANGENT_DICT):
            dist = abs(error - val)
            if dist < min_dist:
                min_dist = dist
                best_idx = i
        return best_idx

    def encode_sample(self, raw_cos, raw_sin):
        output_bytes = b""

        self.cos_history[0] = self.cos_history[1]
        self.cos_history[1] = self.cos_history[2]
        self.cos_history[2] = raw_cos

        zero_crossed = (self.cos_history[1] ^ self.cos_history[2]) < 0

        if zero_crossed:
            raw_signed_sine = max(-2048, min(2047, raw_sin))
            w1 = SYNC_BASE_CODE + (raw_signed_sine + 2048)

            c1 = max(-128, min(127, self.cos_history[0]))
            c2 = max(-128, min(127, self.cos_history[1]))
            w2 = ((c1 & 0xFF) << 8) | (c2 & 0xFF)

            c3 = max(-128, min(127, raw_cos))
            coarse_dr = int(self.filtered_dr >> 4)
            coarse_dr = max(-4, min(3, coarse_dr))

            fingerprint = 0x1A
            byte2_payload = ((fingerprint & 0x1F) << 3) | (coarse_dr & 0x07)
            w3 = ((c3 & 0xFF) << 8) | byte2_payload

            output_bytes = struct.pack(">HHH", w1, w2, w3)

            self.cos_state = raw_cos
            self.sin_state = raw_signed_sine
            self.token_buffer = []
            return output_bytes

        cos_base = self.cos_state - ((self.sin_state * self.filtered_omega) >> 12)
        sin_base = self.sin_state + ((self.cos_state * self.filtered_omega) >> 12)

        cos_pred = cos_base + ((cos_base * self.filtered_dr) // RADIUS)
        sin_pred = sin_base + ((sin_base * self.filtered_dr) // RADIUS)

        err_c = raw_cos - cos_pred
        err_s = raw_sin - sin_pred
        raw_radial = ((cos_pred * err_c) + (sin_pred * err_s)) // RADIUS
        raw_tangent = ((cos_pred * err_s) - (sin_pred * err_c)) // RADIUS

        r_token = self._quantize_radial(raw_radial)
        t_token = self._quantize_tangent(raw_tangent)
        self.token_buffer.append((r_token * 13) + t_token)

        q_radial = r_token - 1
        q_tangent = TANGENT_DICT[t_token]

        self.cos_state = cos_pred + q_radial
        self.sin_state = sin_pred + q_tangent

        self.filtered_omega = (
            (ALPHA_Q15 * q_tangent) + ((32768 - ALPHA_Q15) * self.filtered_omega)
        ) >> 15
        self.filtered_dr = (
            (ALPHA_Q15 * q_radial) + ((32768 - ALPHA_Q15) * self.filtered_dr)
        ) >> 15

        if len(self.token_buffer) == 3:
            t1, t2, t3 = self.token_buffer
            packed_word = ((t1 * 39) + t2) * 39 + t3
            output_bytes = struct.pack(">H", packed_word)
            self.token_buffer = []

        return output_bytes


class Base39Decoder:
    def __init__(self):
        self.cos_state = RADIUS
        self.sin_state = 0
        self.filtered_omega = 0
        self.filtered_dr = 0
        self.is_synchronized = False
        self.frame_buffer = bytearray()
        self.expected_bytes = 2

    def _execute_clean_dual_sync(self, w1, byte2, c1, c2, c3):
        self.cos_state = c3
        self.sin_state = (w1 - SYNC_BASE_CODE) - 2048

        inst_omega = c3 - c2
        self.filtered_omega = inst_omega << 12

        coarse_dr = byte2 & 0x07
        if coarse_dr & 0x04:
            coarse_dr |= 0xF8
        coarse_dr = struct.unpack("b", struct.pack("B", coarse_dr & 0xFF))[0]
        self.filtered_dr = coarse_dr << 12
        self.is_synchronized = True

    def _process_normal_token(self, token):
        r_idx = token // 13
        t_idx = token % 13

        q_radial = r_idx - 1
        q_tangent = TANGENT_DICT[t_idx]

        cos_base = self.cos_state - ((self.sin_state * self.filtered_omega) >> 12)
        sin_base = self.sin_state + ((self.cos_state * self.filtered_omega) >> 12)

        cos_pred = cos_base + ((cos_base * self.filtered_dr) // RADIUS)
        sin_pred = sin_base + ((sin_base * self.filtered_dr) // RADIUS)

        self.cos_state = cos_pred + q_radial
        self.sin_state = sin_pred + q_tangent

        self.filtered_omega = (
            (ALPHA_Q15 * q_tangent) + ((32768 - ALPHA_Q15) * self.filtered_omega)
        ) >> 15
        self.filtered_dr = (
            (ALPHA_Q15 * q_radial) + ((32768 - ALPHA_Q15) * self.filtered_dr)
        ) >> 15

    def parse_bytes(self, incoming_bytes):
        samples_out = []

        for b in incoming_bytes:
            self.frame_buffer.append(b)

            if not self.is_synchronized:
                if len(self.frame_buffer) < 6:
                    continue

                probe_w1 = struct.unpack(">H", self.frame_buffer[0:2])[0]
                probe_b2 = self.frame_buffer[2]
                extracted_fingerprint = (probe_b2 >> 3) & 0x1F

                if (SYNC_BASE_CODE <= probe_w1 <= SYNC_MAX_CODE) and (
                    extracted_fingerprint == 0x1A
                ):
                    w1, w2, w3 = struct.unpack(">HHH", self.frame_buffer[0:6])
                    c1 = struct.unpack("b", struct.pack("B", (w2 >> 8) & 0xFF))[0]
                    c2 = struct.unpack("b", struct.pack("B", w2 & 0xFF))[0]
                    c3 = struct.unpack("b", struct.pack("B", (w3 >> 8) & 0xFF))[0]
                    byte2 = w3 & 0xFF

                    self._execute_clean_dual_sync(w1, byte2, c1, c2, c3)
                    samples_out.append((self.cos_state, self.sin_state))

                    self.frame_buffer = bytearray()
                    self.expected_bytes = 2
                else:
                    self.frame_buffer.pop(0)
                continue

            if len(self.frame_buffer) == 2 and self.expected_bytes == 2:
                current_word = struct.unpack(">H", self.frame_buffer[0:2])[0]
                if SYNC_BASE_CODE <= current_word <= SYNC_MAX_CODE:
                    self.expected_bytes = 6

            if len(self.frame_buffer) == self.expected_bytes:
                if self.expected_bytes == 6:
                    w1, w2, w3 = struct.unpack(">HHH", self.frame_buffer)
                    byte2 = w3 & 0xFF

                    if ((byte2 >> 3) & 0x1F) == 0x1A:
                        c1 = struct.unpack("b", struct.pack("B", (w2 >> 8) & 0xFF))[0]
                        c2 = struct.unpack("b", struct.pack("B", w2 & 0xFF))[0]
                        c3 = struct.unpack("b", struct.pack("B", (w3 >> 8) & 0xFF))[0]

                        self._execute_clean_dual_sync(w1, byte2, c1, c2, c3)
                        samples_out.append((self.cos_state, self.sin_state))
                    else:
                        self.is_synchronized = False
                        self.frame_buffer = bytearray()
                        self.expected_bytes = 2
                        continue
                else:
                    packed_word = struct.unpack(">H", self.frame_buffer)[0]

                    t1 = packed_word // 1521
                    packed_word %= 1521
                    t2 = packed_word // 39
                    t3 = packed_word % 39

                    for token in [t1, t2, t3]:
                        self._process_normal_token(token)
                        samples_out.append((self.cos_state, self.sin_state))

                self.frame_buffer = bytearray()
                self.expected_bytes = 2

        return samples_out


if __name__ == "__main__":
    encoder = Base39Encoder()
    decoder = Base39Decoder()

    mock_sensor_data = [
        (40, 1499),
        (20, 1500),
        (5, 1501),
        (-12, 1498),
        (-28, 1496),
        (-44, 1493),
        (-60, 1490),
    ]

    byte_stream = b""
    for cos, sin in mock_sensor_data:
        frame = encoder.encode_sample(cos, sin)
        if frame:
            byte_stream += frame

    noisy_wire_stream = b"\xaa\xbb" + byte_stream
    decoded_positions = decoder.parse_bytes(noisy_wire_stream)
