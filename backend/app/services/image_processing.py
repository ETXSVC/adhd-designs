import io

from PIL import Image

PRINT_DPI = 300


def compose_print_area(
    source: bytes,
    target_width_px: int,
    target_height_px: int,
    x: float = 0.5,
    y: float = 0.5,
    scale: float = 1.0,
    angle: float = 0.0,
) -> bytes:
    """Composite artwork onto a transparent canvas matching a print area's
    exact pixel dimensions, and stamp 300 DPI metadata so Printify doesn't
    flag it as low-res. `x`/`y` place the artwork's center as a 0..1 fraction
    of the print area (0.5/0.5 = centered); `scale` is relative to the size
    at which the artwork, at its own aspect ratio, fits entirely inside the
    print area (so scale=1 reproduces the old always-centered/fit behavior);
    `angle` rotates it in degrees. The transform is baked into the returned
    pixels, so the caller always uploads to Printify at x=0.5/y=0.5/scale=1/
    angle=0 -- Printify does no further positioning of its own."""

    with Image.open(io.BytesIO(source)) as img:
        img = img.convert("RGBA")

        base_fit = min(target_width_px / img.width, target_height_px / img.height)
        effective_scale = base_fit * scale
        new_size = (max(1, round(img.width * effective_scale)), max(1, round(img.height * effective_scale)))
        resized = img.resize(new_size, Image.LANCZOS)

        if angle % 360:
            resized = resized.rotate(angle, expand=True, resample=Image.BICUBIC)

        canvas = Image.new("RGBA", (target_width_px, target_height_px), (0, 0, 0, 0))
        center_x = round(x * target_width_px)
        center_y = round(y * target_height_px)
        offset = (center_x - resized.width // 2, center_y - resized.height // 2)
        canvas.paste(resized, offset, resized)

        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG", dpi=(PRINT_DPI, PRINT_DPI))
        return buffer.getvalue()


def read_dimensions(source: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(source)) as img:
        return img.width, img.height
