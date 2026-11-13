#!/usr/bin/env python3
"""
PSST icon generator.

Every raster is *drawn* at its target size from the master geometry
(signed-distance rasterisation of rounded rectangles with analytic
anti-aliasing). Nothing is produced by resampling another PNG.

No third-party dependencies: pure Python 3 + zlib. macOS `iconutil`
is used (if present) only to pack already-drawn PNGs into .icns.

Usage: psst_icons.py <output-dir>
"""
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import zlib

# --------------------------------------------------------------------------
# Master geometry (160 x 160 units) — keep in sync with assets/psst-logo.svg
# --------------------------------------------------------------------------
UNIT = 160.0
BG = (0x0F, 0x17, 0x2A)
ACCENT = (0x38, 0xBD, 0xF8)
WHITE = (0xFF, 0xFF, 0xFF)
BG_RX = 36.0
BAR_W = 13.0
BAR_RX = 6.5
CENTER_Y = 80.0
BAR_X = [30.0, 53.0, 76.0, 99.0, 122.0]
BAR_H = [84.0, 56.0, 32.0, 16.0, 8.0]
BAR_COLOR = [ACCENT, WHITE, WHITE, WHITE, WHITE]
BAR_ALPHA = [1.0, 1.0, 0.72, 0.45, 0.22]


def bars():
    """Yield (x, y, w, h, r, rgb, alpha) for each bar in master units."""
    for x, h, c, a in zip(BAR_X, BAR_H, BAR_COLOR, BAR_ALPHA):
        r = min(BAR_RX, h / 2.0, BAR_W / 2.0)
        yield (x, CENTER_Y - h / 2.0, BAR_W, h, r, c, a)


# --------------------------------------------------------------------------
# Rasteriser
# --------------------------------------------------------------------------
def sd_round_rect(px, py, cx, cy, hx, hy, r):
    qx = abs(px - cx) - hx + r
    qy = abs(py - cy) - hy + r
    ox = qx if qx > 0 else 0.0
    oy = qy if qy > 0 else 0.0
    inside = max(qx, qy)
    return math.hypot(ox, oy) + (inside if inside < 0 else 0.0) - r


class Canvas:
    def __init__(self, size, bg=None):
        self.n = size
        # premultiplied-free straight RGBA floats, row-major
        if bg is None:
            self.px = [[0.0, 0.0, 0.0, 0.0] for _ in range(size * size)]
        else:
            self.px = [[bg[0] / 255, bg[1] / 255, bg[2] / 255, 1.0] for _ in range(size * size)]

    def round_rect(self, x, y, w, h, r, rgb, alpha=1.0):
        """Draw a rounded rect given in *pixel* coordinates (floats)."""
        n = self.n
        cx, cy, hx, hy = x + w / 2, y + h / 2, w / 2, h / 2
        r = min(r, hx, hy)
        x0, x1 = max(0, int(math.floor(x)) - 1), min(n, int(math.ceil(x + w)) + 1)
        y0, y1 = max(0, int(math.floor(y)) - 1), min(n, int(math.ceil(y + h)) + 1)
        sr, sg, sb = rgb[0] / 255, rgb[1] / 255, rgb[2] / 255
        for j in range(y0, y1):
            py = j + 0.5
            row = j * n
            for i in range(x0, x1):
                d = sd_round_rect(i + 0.5, py, cx, cy, hx, hy, r)
                cov = 0.5 - d
                if cov <= 0:
                    continue
                if cov > 1:
                    cov = 1.0
                a = cov * alpha
                p = self.px[row + i]
                da = p[3]
                oa = a + da * (1 - a)
                if oa <= 0:
                    continue
                p[0] = (sr * a + p[0] * da * (1 - a)) / oa
                p[1] = (sg * a + p[1] * da * (1 - a)) / oa
                p[2] = (sb * a + p[2] * da * (1 - a)) / oa
                p[3] = oa

    def png(self, alpha=True):
        n = self.n
        raw = bytearray()
        for j in range(n):
            raw.append(0)
            for i in range(n):
                r, g, b, a = self.px[j * n + i]
                if alpha:
                    raw += bytes((round(r * 255), round(g * 255), round(b * 255), round(a * 255)))
                else:  # flatten on background colour (only used for full-bleed art)
                    raw += bytes((round((r * a + BG[0] / 255 * (1 - a)) * 255),
                                  round((g * a + BG[1] / 255 * (1 - a)) * 255),
                                  round((b * a + BG[2] / 255 * (1 - a)) * 255)))
        def chunk(t, d):
            c = struct.pack(">I", len(d)) + t + d
            return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
        ihdr = struct.pack(">IIBBBBB", n, n, 8, 6 if alpha else 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def draw(size, style="rounded", mono=False, transparent_bg=False, content_scale=1.0):
    """
    style:
      rounded   – the master: rounded square (rx 36/160) filling the canvas
      fullbleed – square background filling canvas (iOS / maskable / adaptive)
      macos     – Big Sur grid: 824/1024 rounded square, centred
    mono: draw all bars solid white (notification / monochrome)
    transparent_bg: no background at all
    content_scale: scale of the 160-unit logo square relative to the tile
    """
    c = Canvas(size)
    if style == "macos":
        tile = size * 824 / 1024
        off = (size - tile) / 2
    else:
        tile, off = float(size), 0.0
    k = tile / UNIT
    if not transparent_bg:
        if style == "fullbleed":
            c.round_rect(0, 0, size, size, 0, BG)
        else:
            c.round_rect(off, off, tile, tile, BG_RX * k, BG)
    # logo square may be shrunk inside the tile (e.g. maskable safe zone)
    ks = k * content_scale
    inner = UNIT * ks
    ioff = off + (tile - inner) / 2
    for (x, y, w, h, r, rgb, a) in bars():
        if mono:
            rgb, a = WHITE, 1.0
        c.round_rect(ioff + x * ks, ioff + y * ks, w * ks, h * ks, r * ks, rgb, a)
    return c


# --------------------------------------------------------------------------
# Container formats
# --------------------------------------------------------------------------
def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def ico(pngs):
    """pngs: list of (size, png_bytes). PNG-compressed ICO entries."""
    hdr = struct.pack("<HHH", 0, 1, len(pngs))
    off = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for s, data in pngs:
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), off)
        off += len(data)
        blobs += data
    return hdr + entries + blobs


def icns_fallback(items):
    """Pack PNGs into .icns without iconutil. items: list of (ostype, png)."""
    body = b"".join(t.encode() + struct.pack(">I", len(d) + 8) + d for t, d in items)
    return b"icns" + struct.pack(">I", len(body) + 8) + body


# --------------------------------------------------------------------------
# Vector outputs (Android VectorDrawable, SVG variants)
# --------------------------------------------------------------------------
def vd_round_rect(x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    f = lambda v: ("%.3f" % v).rstrip("0").rstrip(".")
    return (f"M{f(x + r)},{f(y)} H{f(x + w - r)} A{f(r)},{f(r)} 0 0 1 {f(x + w)},{f(y + r)} "
            f"V{f(y + h - r)} A{f(r)},{f(r)} 0 0 1 {f(x + w - r)},{f(y + h)} "
            f"H{f(x + r)} A{f(r)},{f(r)} 0 0 1 {f(x)},{f(y + h - r)} "
            f"V{f(y + r)} A{f(r)},{f(r)} 0 0 1 {f(x + r)},{f(y)} Z")


def android_foreground(mono=False, viewport=108.0, scale=0.5):
    off = (viewport - UNIT * scale) / 2
    paths = []
    for (x, y, w, h, r, rgb, a) in bars():
        color = "#FFFFFFFF" if mono else "#%02X%02X%02X%02X" % (round(a * 255), *rgb)
        d = vd_round_rect(off + x * scale, off + y * scale, w * scale, h * scale, r * scale)
        paths.append(f'    <path android:fillColor="{color}" android:pathData="{d}"/>')
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!-- Generated by scripts/make-icons.sh from assets/psst-logo.svg geometry. Do not edit. -->\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            f'    android:width="{viewport:g}dp" android:height="{viewport:g}dp"\n'
            f'    android:viewportWidth="{viewport:g}" android:viewportHeight="{viewport:g}">\n'
            + "\n".join(paths) + "\n</vector>\n")


def android_notification():
    # 24dp status-bar icon: solid white bars, content fits in 20dp
    vp = 24.0
    xs = BAR_X[0]
    span = BAR_X[-1] + BAR_W - xs           # 105
    s = 20.0 / span
    ox = (vp - span * s) / 2 - xs * s
    oy = vp / 2 - CENTER_Y * s
    paths = []
    for (x, y, w, h, r, rgb, a) in bars():
        d = vd_round_rect(ox + x * s, oy + y * s, w * s, h * s, r * s)
        paths.append(f'    <path android:fillColor="#FFFFFFFF" android:pathData="{d}"/>')
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<!-- Generated by scripts/make-icons.sh. Monochrome notification icon. Do not edit. -->\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:width="24dp" android:height="24dp"\n'
            '    android:viewportWidth="24" android:viewportHeight="24">\n'
            + "\n".join(paths) + "\n</vector>\n")


def svg_variant(style="rounded", mono=False, content_scale=1.0, transparent_bg=False):
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">']
    if not transparent_bg:
        rx = 0 if style == "fullbleed" else BG_RX
        out.append(f'  <rect width="160" height="160" rx="{rx:g}" fill="#0F172A"/>')
    off = (UNIT - UNIT * content_scale) / 2
    for (x, y, w, h, r, rgb, a) in bars():
        fill = "#FFFFFF" if mono else "#%02X%02X%02X" % rgb
        op = 1.0 if mono else a
        out.append(f'  <rect x="{off + x * content_scale:g}" y="{off + y * content_scale:g}" '
                   f'width="{w * content_scale:g}" height="{h * content_scale:g}" rx="{r * content_scale:g}" '
                   f'fill="{fill}" fill-opacity="{op:g}"/>')
    out.append("</svg>\n")
    return "\n".join(out)


def wordmark_svg(on_dark_bg=False):
    """Three tallest bars + lowercase 'psst' drawn as round-capped white strokes."""
    out_bars = []
    for (x, y, w, h, r, rgb, a) in list(bars())[:3]:
        fill = "#%02X%02X%02X" % rgb
        out_bars.append(f'  <rect x="{x - 10:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{r:g}" '
                        f'fill="{fill}" fill-opacity="{a:g}"/>')
    # stroke centre-lines: x-height 62..98 (outer 56..104), descender to 124
    P, S1, S2, T = 100, 158, 212, 262
    def s_glyph(S):
        return (f"M{S + 32},68 C{S + 28},63 {S + 22},62 {S + 16},62 C{S + 6},62 {S},66 {S},71 "
                f"C{S},77 {S + 6},79 {S + 16},80 C{S + 26},81 {S + 32},83 {S + 32},89 "
                f"C{S + 32},95 {S + 26},98 {S + 16},98 C{S + 10},98 {S + 3},97 {S},92")
    glyphs = [
        f"M{P},62 V124",                                            # p stem
        f"M{P},80 a18,18 0 1 0 36,0 a18,18 0 1 0 -36,0",            # p bowl
        s_glyph(S1), s_glyph(S2),
        f"M{T},46 V88 C{T},95 {T + 4},98 {T + 12},98",               # t stem
        f"M{T - 10},62 H{T + 14}",                                   # t bar
    ]
    width = 300
    bg = f'  <rect width="{width}" height="160" rx="36" fill="#0F172A"/>\n' if on_dark_bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="160" viewBox="0 0 {width} 160">\n'
            f'  <title>psst</title>\n{bg}' + "\n".join(out_bars) + "\n"
            '  <g fill="none" stroke="#FFFFFF" stroke-width="12" stroke-linecap="round" stroke-linejoin="round">\n'
            + "\n".join(f'    <path d="{d}"/>' for d in glyphs) + "\n  </g>\n</svg>\n")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main(out):
    if os.path.isdir(out):
        shutil.rmtree(out)
    cache = {}

    def png(size, style="rounded", alpha=True, **kw):
        key = (size, style, alpha, tuple(sorted(kw.items())))
        if key not in cache:
            cache[key] = draw(size, style, **kw).png(alpha=alpha)
        return cache[key]

    # ---- web / PWA ----------------------------------------------------
    for s in (16, 32, 48):
        write(f"{out}/web/favicon-{s}x{s}.png", png(s))
    write(f"{out}/web/favicon.ico", ico([(s, png(s)) for s in (16, 32, 48)]))
    write(f"{out}/web/apple-touch-icon.png", png(180, "fullbleed", alpha=False))
    for s in (192, 512):
        write(f"{out}/web/icon-{s}.png", png(s))
        write(f"{out}/web/icon-maskable-{s}.png", png(s, "fullbleed", alpha=False, content_scale=0.8))
    for s in (24, 120, 144, 152, 180, 192, 256, 512):  # sizes used by element-web vector-icons
        write(f"{out}/web/vector-icons/{s}.png", png(s))
    with open(f"{out}/web/favicon.svg", "w") as f:
        f.write(svg_variant())

    # ---- Windows .ico (16–256) ----------------------------------------
    write(f"{out}/windows/psst.ico", ico([(s, png(s)) for s in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)]))
    for s in (44, 50, 150, 310):  # appx / tiles
        write(f"{out}/windows/tile-{s}.png", png(s))

    # ---- macOS .icns ---------------------------------------------------
    iconset = f"{out}/macos/psst.iconset"
    spec = [(16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
            (128, "128x128"), (256, "128x128@2x"), (256, "256x256"), (512, "256x256@2x"),
            (512, "512x512"), (1024, "512x512@2x")]
    for s, name in spec:
        write(f"{iconset}/icon_{name}.png", png(s, "macos"))
    write(f"{out}/macos/icon-1024.png", png(1024, "macos"))
    icns = f"{out}/macos/psst.icns"
    if shutil.which("iconutil"):
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    else:
        types = {16: "icp4", 32: "icp5", 64: "icp6", 128: "ic07", 256: "ic08", 512: "ic09", 1024: "ic10"}
        write(icns, icns_fallback([(types[s], png(s, "macos")) for s in sorted(types)]))

    # ---- Linux (electron-builder) -------------------------------------
    for s in (16, 24, 32, 48, 64, 96, 128, 256, 512):
        write(f"{out}/linux/{s}x{s}.png", png(s))

    # ---- iOS AppIcon (no alpha) ---------------------------------------
    ios_dir = f"{out}/ios/AppIcon.appiconset"
    images = []
    ios_spec = [  # (idiom, point size, scales)
        ("iphone", 20, (2, 3)), ("iphone", 29, (2, 3)), ("iphone", 38, (2, 3)), ("iphone", 40, (2, 3)),
        ("iphone", 60, (2, 3)), ("iphone", 64, (2, 3)), ("iphone", 68, (2,)), ("iphone", 76, (2,)),
        ("ipad", 20, (1, 2)), ("ipad", 29, (1, 2)), ("ipad", 40, (1, 2)), ("ipad", 76, (1, 2)),
        ("ipad", 83.5, (2,)),
    ]
    for idiom, pt, scales in ios_spec:
        for sc in scales:
            px = int(round(pt * sc))
            fn = f"icon-{pt:g}@{sc}x.png"
            write(f"{ios_dir}/{fn}", png(px, "fullbleed", alpha=False))
            images.append({"filename": fn, "idiom": idiom, "scale": f"{sc}x", "size": f"{pt:g}x{pt:g}"})
    write(f"{ios_dir}/icon-1024.png", png(1024, "fullbleed", alpha=False))
    images.append({"filename": "icon-1024.png", "idiom": "ios-marketing", "scale": "1x", "size": "1024x1024"})
    # single-size entry used by modern Xcode targets
    images.append({"filename": "icon-1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"})
    write(f"{ios_dir}/Contents.json",
          json.dumps({"images": images, "info": {"author": "psst make-icons", "version": 1}}, indent=2).encode())

    # ---- Android ------------------------------------------------------
    a = f"{out}/android/res"
    write(f"{a}/drawable/ic_launcher_foreground.xml", android_foreground().encode())
    write(f"{a}/drawable/ic_launcher_monochrome.xml", android_foreground(mono=True).encode())
    write(f"{a}/drawable/ic_notification.xml", android_notification().encode())
    write(f"{a}/values/ic_launcher_background.xml",
          b'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
          b'    <color name="ic_launcher_background">#0F172A</color>\n</resources>\n')
    adaptive = ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                '    <background android:drawable="@color/ic_launcher_background"/>\n'
                '    <foreground android:drawable="@drawable/ic_launcher_foreground"/>\n'
                '    <monochrome android:drawable="@drawable/ic_launcher_monochrome"/>\n'
                '</adaptive-icon>\n').encode()
    write(f"{a}/mipmap-anydpi-v26/ic_launcher.xml", adaptive)
    write(f"{a}/mipmap-anydpi-v26/ic_launcher_round.xml", adaptive)
    for dpi, s in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
        write(f"{a}/mipmap-{dpi}/ic_launcher.png", png(s))
        write(f"{a}/mipmap-{dpi}/ic_launcher_round.png", png(s))  # legacy (<26) fallback
    for dpi, s in (("mdpi", 24), ("hdpi", 36), ("xhdpi", 48), ("xxhdpi", 72), ("xxxhdpi", 96)):
        write(f"{a}/drawable-{dpi}/ic_notification_png.png", png(s, mono=True, transparent_bg=True))
    write(f"{out}/android/play-store-512.png", png(512, "fullbleed", alpha=False))

    # ---- SVG variants & wordmark --------------------------------------
    os.makedirs(f"{out}/svg", exist_ok=True)
    with open(f"{out}/svg/psst-logo-fullbleed.svg", "w") as f:
        f.write(svg_variant("fullbleed"))
    with open(f"{out}/svg/psst-glyph-mono.svg", "w") as f:
        f.write(svg_variant(mono=True, transparent_bg=True))
    with open(f"{out}/svg/psst-wordmark.svg", "w") as f:
        f.write(wordmark_svg())
    with open(f"{out}/svg/psst-wordmark-on-dark.svg", "w") as f:
        f.write(wordmark_svg(on_dark_bg=True))
    print(f"icons written to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "assets/generated")
