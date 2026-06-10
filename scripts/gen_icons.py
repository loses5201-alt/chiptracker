"""
PWA 圖示產生器 — 純標準函式庫(zlib + struct)直接寫 PNG,不依賴 Pillow。

圖案:靛藍漸層圓角方塊 + 三根白色上升量柱 + 金色突破箭頭(呼應「跟著大戶」)。
執行:python scripts/gen_icons.py   → 產出 assets/icons/icon-{180,192,512,512-maskable}.png
"""
from __future__ import annotations
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "icons"

# 色票(RGB)
BG_TOP = (79, 70, 229)      # #4f46e5
BG_BOT = (129, 140, 248)    # #818cf8
BAR = (255, 255, 255)
GOLD = (251, 191, 36)       # #fbbf24


def png_bytes(width: int, height: int, pixels: list[list[tuple]]) -> bytes:
    """RGBA 像素陣列 → PNG 二進位。"""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    raw = b"".join(b"\x00" + b"".join(bytes(px) for px in row) for row in pixels)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def draw_icon(size: int, maskable: bool = False) -> list[list[tuple]]:
    """逐像素畫圖示。maskable 版圖案內縮(Android 自適應圖示會裁掉外圈 ~20%)。"""
    s = size
    radius = 0 if maskable else s * 0.22          # maskable 由系統裁形,自己不留圓角
    pad = s * 0.18 if maskable else 0.0           # maskable 安全區內縮
    # 三根上升量柱 + 箭頭的相對佈局(以非 maskable 的 0~1 座標為準,再依 pad 縮放)
    def rel(v: float) -> float:
        return pad + v * (s - 2 * pad)

    base_y = rel(0.80)
    bars = [  # (左x, 寬, 高) 相對座標
        (0.18, 0.14, 0.22),
        (0.40, 0.14, 0.38),
        (0.62, 0.14, 0.56),
    ]
    bar_rects = [(rel(x), base_y - (rel(x + 0) - rel(0)) * 0 - h * (s - 2 * pad), rel(x) + w * (s - 2 * pad), base_y)
                 for x, w, h in bars]
    # 金色箭頭:從第一根柱頂往右上到右上角附近
    ax1, ay1 = rel(0.22), rel(0.52)
    ax2, ay2 = rel(0.80), rel(0.18)
    arrow_w = s * 0.045

    def in_rounded_rect(x: float, y: float) -> bool:
        if radius <= 0:
            return True
        rx = min(x, s - 1 - x)
        ry = min(y, s - 1 - y)
        if rx >= radius or ry >= radius:
            return True
        dx, dy = radius - rx, radius - ry
        return dx * dx + dy * dy <= radius * radius

    def dist_to_segment(px: float, py: float) -> float:
        vx, vy = ax2 - ax1, ay2 - ay1
        t = max(0.0, min(1.0, ((px - ax1) * vx + (py - ay1) * vy) / (vx * vx + vy * vy)))
        cx, cy = ax1 + t * vx, ay1 + t * vy
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    rows = []
    for y in range(s):
        row = []
        for x in range(s):
            if not in_rounded_rect(x, y):
                row.append((0, 0, 0, 0))
                continue
            # 背景垂直漸層
            t = y / s
            r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
            g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
            b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
            px = (r, g, b, 255)
            for (x1, y1, x2, y2) in bar_rects:
                if x1 <= x <= x2 and y1 <= y <= y2:
                    px = (*BAR, 255)
                    break
            d = dist_to_segment(x, y)
            if d <= arrow_w:
                px = (*GOLD, 255)
            # 箭頭頭部(右上端的三角形,粗略用距端點 + 在線上方判斷)
            if ((x - ax2) ** 2 + (y - ay2) ** 2) ** 0.5 <= arrow_w * 2.2:
                px = (*GOLD, 255)
            row.append(px)
        rows.append(row)
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name, maskable in [
        (180, "icon-180.png", False),
        (192, "icon-192.png", False),
        (512, "icon-512.png", False),
        (512, "icon-512-maskable.png", True),
    ]:
        path = OUT / name
        path.write_bytes(png_bytes(size, size, draw_icon(size, maskable)))
        print(f"OK {path.name} ({size}x{size}, {path.stat().st_size} bytes)")  # 用 ASCII,cp950 終端不吃 ✓


if __name__ == "__main__":
    main()
