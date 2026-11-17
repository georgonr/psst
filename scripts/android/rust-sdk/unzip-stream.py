#!/usr/bin/env python3
"""Extract a zip by walking its local file headers (like `jar xf`), ignoring the central directory.

The official sdk-android sources jar / AAR on Maven contain duplicate entries whose data overlap, which unzip and
Python's zipfile reject as a possible zip bomb. Later duplicates overwrite earlier ones.
    unzip-stream.py <archive> <dest-dir>
"""
import os
import struct
import sys
import zlib

src, dest = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
pos, count = 0, 0
while data[pos:pos + 4] == b"PK\x03\x04":
    (_, _, flags, method, _, _, crc, csize, usize, nlen, xlen) = struct.unpack("<IHHHHHIIIHH", data[pos:pos + 30])
    name = data[pos + 30:pos + 30 + nlen].decode("utf-8")
    start = pos + 30 + nlen + xlen
    if method == 8:
        d = zlib.decompressobj(-15)
        out = d.decompress(data[start:start + csize] if not flags & 8 else data[start:])
        used = (csize if not flags & 8 else len(data) - start - len(d.unused_data))
    elif method == 0:
        if flags & 8:
            raise SystemExit(f"stored entry with data descriptor not supported: {name}")
        out, used = data[start:start + csize], csize
    else:
        raise SystemExit(f"unsupported method {method}: {name}")
    pos = start + used
    if flags & 8:  # data descriptor, optional signature
        pos += 16 if data[pos:pos + 4] == b"PK\x07\x08" else 12
    if name.endswith("/"):
        continue
    path = os.path.normpath(os.path.join(dest, name))
    if not path.startswith(os.path.normpath(dest) + os.sep):
        raise SystemExit(f"unsafe path: {name}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)
    count += 1
print(f"{count} files extracted from {src}")
