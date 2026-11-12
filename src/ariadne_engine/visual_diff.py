"""Dependency-free screenshot comparison (Ariadne 2.4C).

A visual regression is a controlled comparison between two captures, not a
claim that two images "look similar". This module decodes the PNG bytes the
browser actually produced, compares pixels at a declared per-channel threshold,
reports the changed-pixel ratio and bounding box, and supports explicit masks
for justified dynamic regions.

It deliberately does not bundle an image library or a perceptual model. A
per-channel RGBA comparison is deterministic, explainable and sufficient for
the regression question -- *did this region change?* -- which is the only
question a pixel measurement can answer. Visual quality remains a review
judgement; pixel similarity never approves a design.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path
from typing import Mapping, Sequence


class PngError(ValueError):
    """The bytes are not a PNG this comparator can decode."""


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw: bytes, *, width: int, height: int, bpp: int) -> bytes:
    stride = width * bpp
    expected = height * (stride + 1)
    if len(raw) < expected:
        raise PngError(f"PNG image data is truncated: {len(raw)} bytes, expected {expected}")
    output = bytearray(height * stride)
    offset = 0
    previous = bytearray(stride)
    for row in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        if filter_type == 0:
            pass
        elif filter_type == 1:
            for index in range(stride):
                left = line[index - bpp] if index >= bpp else 0
                line[index] = (line[index] + left) & 0xFF
        elif filter_type == 2:
            for index in range(stride):
                line[index] = (line[index] + previous[index]) & 0xFF
        elif filter_type == 3:
            for index in range(stride):
                left = line[index - bpp] if index >= bpp else 0
                line[index] = (line[index] + ((left + previous[index]) // 2)) & 0xFF
        elif filter_type == 4:
            for index in range(stride):
                left = line[index - bpp] if index >= bpp else 0
                upper_left = previous[index - bpp] if index >= bpp else 0
                line[index] = (line[index] + _paeth(left, previous[index], upper_left)) & 0xFF
        else:
            raise PngError(f"PNG uses an unsupported filter type: {filter_type}")
        output[row * stride:(row + 1) * stride] = line
        previous = line
    return bytes(output)


def decode_png(payload: bytes) -> dict:
    """Decode a non-interlaced 8-bit PNG into RGBA pixels.

    Only the shapes a browser screenshot produces are supported. A 16-bit,
    palette or interlaced image is refused by name rather than silently
    compared as if it were the same kind of artifact.
    """
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PngError("not a PNG: the signature is missing")
    offset = 8
    width = height = 0
    bit_depth = color_type = 0
    interlace = 0
    compressed = bytearray()
    while offset + 8 <= len(payload):
        length = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        data = payload[offset + 8:offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            if len(data) != 13:
                raise PngError("PNG IHDR is malformed")
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", data)
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            break
    if not width or not height:
        raise PngError("PNG has no IHDR dimensions")
    if bit_depth != 8:
        raise PngError(f"only 8-bit PNGs are compared here; this one is {bit_depth}-bit")
    if interlace:
        raise PngError("interlaced PNGs are not compared here")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise PngError(f"unsupported PNG colour type: {color_type}")
    try:
        raw = zlib.decompress(bytes(compressed))
    except zlib.error as exc:
        raise PngError(f"PNG image data could not be decompressed: {exc}") from exc
    pixels = _unfilter(raw, width=width, height=height, bpp=channels)
    if color_type == 6:
        rgba = pixels
    else:
        rgba = bytearray(width * height * 4)
        for index in range(width * height):
            if color_type == 2:
                r, g, b = pixels[index * 3:index * 3 + 3]
                a = 255
            elif color_type == 0:
                r = g = b = pixels[index]
                a = 255
            elif color_type == 4:
                r = g = b = pixels[index * 2]
                a = pixels[index * 2 + 1]
            else:  # pragma: no cover - guarded by the channel map
                raise PngError("unsupported conversion")
            rgba[index * 4:index * 4 + 4] = bytes((r, g, b, a))
        pixels = bytes(rgba)
    return {
        "width": width,
        "height": height,
        "color_type": color_type,
        "channels": channels,
        "pixels": pixels,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _masked(x: int, y: int, masks: Sequence[Mapping]) -> bool:
    for mask in masks or ():
        try:
            left = int(mask.get("x", 0))
            top = int(mask.get("y", 0))
            width = int(mask.get("width", mask.get("w", 0)))
            height = int(mask.get("height", mask.get("h", 0)))
        except (TypeError, ValueError):
            raise PngError("a comparison mask has non-numeric geometry")
        if left <= x < left + width and top <= y < top + height:
            return True
    return False


def compare_png(
    before: bytes,
    after: bytes,
    *,
    threshold: float = 0.1,
    masks: Sequence[Mapping] = (),
) -> dict:
    """Compare two PNG byte strings at a declared per-channel threshold."""
    if not 0 <= float(threshold) <= 1:
        raise PngError("threshold must be between 0 and 1")
    left = decode_png(before)
    right = decode_png(after)
    if (left["width"], left["height"]) != (right["width"], right["height"]):
        return {
            "verdict": "INCOMPATIBLE",
            "reason": (
                f"image dimensions differ: {left['width']}x{left['height']} vs "
                f"{right['width']}x{right['height']}; this is not a comparison of the same viewport"
            ),
            "before": {"width": left["width"], "height": left["height"], "sha256": left["sha256"]},
            "after": {"width": right["width"], "height": right["height"], "sha256": right["sha256"]},
            "changed_pixels": 0,
            "total_pixels": 0,
            "diff_ratio": None,
        }
    limit = int(round(float(threshold) * 255))
    changed = 0
    total = left["width"] * left["height"]
    first = None
    last = None
    max_delta = 0
    left_pixels = left["pixels"]
    right_pixels = right["pixels"]
    for y in range(left["height"]):
        for x in range(left["width"]):
            if _masked(x, y, masks):
                continue
            index = (y * left["width"] + x) * 4
            delta = max(
                abs(left_pixels[index + channel] - right_pixels[index + channel])
                for channel in range(4)
            )
            max_delta = max(max_delta, delta)
            if delta > limit:
                changed += 1
                first = (x, y) if first is None else first
                last = (x, y)
    bounding = None
    if first is not None and last is not None:
        bounding = {
            "x": first[0], "y": first[1],
            "width": last[0] - first[0] + 1,
            "height": last[1] - first[1] + 1,
        }
    return {
        "verdict": "IDENTICAL" if changed == 0 else "CHANGED",
        "before": {"width": left["width"], "height": left["height"], "sha256": left["sha256"]},
        "after": {"width": right["width"], "height": right["height"], "sha256": right["sha256"]},
        "changed_pixels": changed,
        "total_pixels": total,
        "diff_ratio": round(changed / total, 8) if total else None,
        "max_channel_delta": max_delta,
        "threshold": float(threshold),
        "masked_regions": len(masks or ()),
        "bounding_box": bounding,
        "basis": (
            "per-channel RGBA comparison of the rendered PNGs; a pixel difference is not a "
            "quality judgement and does not approve a design"
        ),
    }


def compare_files(
    before: Path,
    after: Path,
    *,
    threshold: float = 0.1,
    masks: Sequence[Mapping] = (),
) -> dict:
    return compare_png(Path(before).read_bytes(), Path(after).read_bytes(), threshold=threshold, masks=masks)
