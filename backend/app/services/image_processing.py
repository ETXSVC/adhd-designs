import io

from PIL import Image

PRINT_DPI = 300


def fit_to_print_area(source: bytes, target_width_px: int, target_height_px: int) -> bytes:
    """Scale artwork to fit inside a print area's exact pixel dimensions,
    preserving aspect ratio, centered on a transparent canvas of that exact
    size, and stamp 300 DPI metadata so Printify doesn't flag it as low-res.
    Returns PNG bytes."""

    with Image.open(io.BytesIO(source)) as img:
        img = img.convert("RGBA")

        scale = min(target_width_px / img.width, target_height_px / img.height)
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        resized = img.resize(new_size, Image.LANCZOS)

        canvas = Image.new("RGBA", (target_width_px, target_height_px), (0, 0, 0, 0))
        offset = ((target_width_px - new_size[0]) // 2, (target_height_px - new_size[1]) // 2)
        canvas.paste(resized, offset, resized)

        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG", dpi=(PRINT_DPI, PRINT_DPI))
        return buffer.getvalue()


def read_dimensions(source: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(source)) as img:
        return img.width, img.height
