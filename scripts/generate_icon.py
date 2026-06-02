import math
import struct
import zlib
from pathlib import Path


def _png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _make_png(size):
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            cx = (x + 0.5) / size
            cy = (y + 0.5) / size
            margin = 0.07
            radius = 0.18
            inside = margin <= cx <= 1 - margin and margin <= cy <= 1 - margin
            corner_dx = max(margin - cx, 0, cx - (1 - margin))
            corner_dy = max(margin - cy, 0, cy - (1 - margin))
            rounded = inside or math.hypot(corner_dx, corner_dy) <= radius

            if rounded:
                r = int(28 + 18 * cy)
                g = int(92 + 35 * (1 - cy))
                b = int(190 + 45 * (1 - cx))
                a = 255
            else:
                r = g = b = a = 0

            if rounded and (0.17 < cy < 0.28 or 0.72 < cy < 0.83) and 0.16 < cx < 0.84:
                r, g, b = 15, 34, 72
            if rounded and 0.42 < cy < 0.66 and 0.18 < cx < 0.82:
                r, g, b = 248, 250, 252
            if rounded and ((0.48 < cy < 0.52) or (0.57 < cy < 0.61)) and 0.28 < cx < 0.72:
                r, g, b = 20, 45, 95
            if rounded and 0.31 < cy < 0.42 and 0.42 < cx < 0.58 and abs(cy - 0.365) < (cx - 0.42) * 0.9:
                r, g, b = 255, 213, 74

            row.extend([r, g, b, a])
        rows.append(bytes(row))

    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )


def generate_icon(output_path):
    images = [(256, _make_png(256)), (64, _make_png(64)), (32, _make_png(32)), (16, _make_png(16))]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = []
    payload = []

    for size, data in images:
        size_byte = 0 if size == 256 else size
        entries.append(struct.pack("<BBBBHHII", size_byte, size_byte, 0, 0, 1, 32, len(data), offset))
        payload.append(data)
        offset += len(data)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header + b"".join(entries) + b"".join(payload))
    return output


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    icon_path = generate_icon(project_root / "assets" / "app.ico")
    print(f"Generated {icon_path}")
