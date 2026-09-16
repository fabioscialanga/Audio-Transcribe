"""Generate the multi-resolution Windows icon used by the packaged app."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "icon.ico"


def rounded_rectangle(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def create_icon() -> None:
    canvas = Image.new("RGBA", (256, 256), "#0b1020")
    draw = ImageDraw.Draw(canvas)
    rounded_rectangle(draw, (22, 22, 234, 234), 48, "#786cff")
    bars = [(62, 103, 78, 153), (88, 78, 104, 178), (114, 55, 142, 201),
            (152, 82, 168, 174), (178, 105, 194, 151)]
    for index, box in enumerate(bars):
        radius = 14 if index == 2 else 8
        rounded_rectangle(draw, box, radius, "white")
    canvas.save(OUTPUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                               (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    create_icon()
    print(OUTPUT)
