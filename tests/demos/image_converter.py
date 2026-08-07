"""Draw a pixelated image as BOX controls inside a named group.

Needs Pillow, which is not a tosclib dependency:

    pip install pillow
    python tests/demos/image_converter.py tests/data/test.tosc tests/data/logo.jpg canvas

Keep the image size modest. At 64x64 this emits 4096 controls; much beyond that
and both the file size and the editor's performance suffer.
"""

import argparse
from pathlib import Path

from PIL import Image

import py2tosc

IMAGE_SIZE = 64
PIXEL_SIZE = 4


def pixelate(image_path: str, size: int) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Scale an image down and return its width, height and RGB pixels."""
    image = Image.open(image_path).convert("RGB")
    ratio = min(image.size) / size
    width, height = int(image.size[0] / ratio), int(image.size[1] / ratio)
    small = image.resize((width, height), resample=Image.Resampling.BILINEAR)

    raw = small.tobytes()
    pixels = [tuple(raw[i : i + 3]) for i in range(0, len(raw), 3)]
    return width, height, pixels


def main(input_path: str, output_path: Path, image_path: str, canvas_name: str) -> None:
    doc = py2tosc.load(input_path)

    canvas = doc.find(canvas_name)
    if canvas is None:
        raise SystemExit(f"no group named {canvas_name!r} in {input_path}")

    width, height, pixels = pixelate(image_path, IMAGE_SIZE)

    for index, (r, g, b) in enumerate(pixels):
        x, y = index % width, index // width
        canvas.add(
            py2tosc.box(
                name=f"p{x}_{y}",
                color=(r, g, b),
                frame=(x * PIXEL_SIZE, y * PIXEL_SIZE, PIXEL_SIZE, PIXEL_SIZE),
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    print(f"drew {width * height} boxes ({width}x{height}) -> {output_path}")


def parse_args() -> argparse.Namespace:
    """Read the command line, so a missing path is a message and not a crash."""
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="the layout to read")
    parser.add_argument("image", help="the picture to draw")
    parser.add_argument("canvas", help="the group to draw it into")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("build") / f"{Path(__file__).stem}.tosc",
        help="where to write the layout (default: %(default)s)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.input, args.output, args.image, args.canvas)
