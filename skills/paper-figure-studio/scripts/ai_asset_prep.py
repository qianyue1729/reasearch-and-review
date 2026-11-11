#!/usr/bin/env python3
"""Clean and frame localized AI-generated micro-assets (strip white/solid background, tight crop, resize, round corners)."""
from __future__ import annotations

import argparse
from collections import deque
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def flood_remove_bg(img: Image.Image, tol: float = 30.0, feather: float = 14.0) -> Image.Image:
    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.float32)
    h, w, _ = arr.shape
    rgb = arr[:, :, :3]

    # Estimate background color from outer border median
    border_pixels = np.concatenate([
        rgb[0, :, :], rgb[h - 1, :, :], rgb[:, 0, :], rgb[:, w - 1, :]
    ], axis=0)
    bg_color = np.median(border_pixels, axis=0)

    dist = np.linalg.norm(rgb - bg_color[None, None, :], axis=2)
    candidate = dist <= (tol + feather)

    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if candidate[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if candidate[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))

    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and candidate[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    alpha = arr[:, :, 3].copy()
    hard_bg = visited & (dist <= tol)
    soft_bg = visited & (dist > tol) & (dist <= tol + feather)
    alpha[hard_bg] = 0.0
    if np.any(soft_bg):
        ramp = (dist[soft_bg] - tol) / max(feather, 1.0)
        alpha[soft_bg] = np.clip(ramp * 255.0, 0.0, 255.0)

    arr[:, :, 3] = alpha
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def tight_crop_rgba(img: Image.Image, pad: int = 10) -> Image.Image:
    arr = np.array(img)
    if arr.shape[2] == 4:
        mask = arr[:, :, 3] > 12
    else:
        mask = np.any(arr[:, :, :3] < 245, axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return img
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(img.width, int(xs.max()) + 1 + pad)
    y1 = min(img.height, int(ys.max()) + 1 + pad)
    return img.crop((x0, y0, x1, y1))


def apply_rounded_mask(img: Image.Image, radius: int, border_rgb: tuple[int, int, int] | None = None, border_px: int = 0) -> Image.Image:
    rgba = img.convert("RGBA")
    mask = Image.new("L", rgba.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, rgba.width - 1, rgba.height - 1), radius=radius, fill=255)
    existing_a = np.array(rgba)[:, :, 3].astype(np.float32) / 255.0
    mask_a = np.array(mask).astype(np.float32) / 255.0
    out_arr = np.array(rgba)
    out_arr[:, :, 3] = (existing_a * mask_a * 255.0).astype(np.uint8)
    out = Image.fromarray(out_arr, mode="RGBA")
    if border_rgb and border_px > 0:
        bdraw = ImageDraw.Draw(out)
        bdraw.rounded_rectangle(
            (border_px // 2, border_px // 2, out.width - 1 - border_px // 2, out.height - 1 - border_px // 2),
            radius=radius,
            outline=(*border_rgb, 255),
            width=border_px,
        )
    return out


def process_asset(
    src: Path,
    dst: Path,
    remove_bg: bool = True,
    tol: float = 30.0,
    pad: int = 8,
    square_pad: bool = True,
    max_px: int = 512,
    rounded_radius: int = 0,
) -> dict:
    im = Image.open(src).convert("RGBA")
    orig_size = im.size
    if remove_bg:
        im = flood_remove_bg(im, tol=tol)
    im = tight_crop_rgba(im, pad=pad)

    if square_pad:
        side = max(im.width, im.height)
        canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
        canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
        im = canvas

    if max(im.width, im.height) > max_px:
        scale = max_px / max(im.width, im.height)
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.Resampling.LANCZOS)

    if rounded_radius > 0:
        im = apply_rounded_mask(im, radius=rounded_radius)

    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, format="PNG", optimize=True)
    alpha_arr = np.array(im)[:, :, 3]
    transparent_ratio = float(np.mean(alpha_arr < 16))
    return {
        "input": str(src),
        "output": str(dst),
        "orig_size": list(orig_size),
        "final_size": [im.width, im.height],
        "transparent_ratio": round(transparent_ratio, 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Clean and prepare localized AI micro-assets for PPTX vector figures.")
    ap.add_argument("--input", required=True, help="Raw PNG/JPG path from image-generator.")
    ap.add_argument("--output", required=True, help="Cleaned RGBA PNG output path.")
    ap.add_argument("--keep-bg", action="store_true", help="Keep background (for rectangular photo/patch crops).")
    ap.add_argument("--tol", type=float, default=30.0, help="Background flood-fill RGB distance tolerance.")
    ap.add_argument("--pad", type=int, default=8, help="Pixel padding around tight crop.")
    ap.add_argument("--no-square", action="store_true", help="Do not center-pad into a 1:1 square icon frame.")
    ap.add_argument("--max-px", type=int, default=512, help="Max output pixel dimension (prevents bloated PDFs).")
    ap.add_argument("--rounded", type=int, default=0, help="Optional rounded-rectangle mask radius in pixels.")
    args = ap.parse_args()

    res = process_asset(
        src=Path(args.input),
        dst=Path(args.output),
        remove_bg=not args.keep_bg,
        tol=args.tol,
        pad=args.pad,
        square_pad=not args.no_square,
        max_px=args.max_px,
        rounded_radius=args.rounded,
    )
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
