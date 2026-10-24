"""Maakt assets/icon.ico: twee vingers in Goku-kleuren. Draaien: python tools/make_icon.py"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
ORANGE = (240, 138, 36, 255)
BLUE = (31, 79, 160, 255)
WHITE = (255, 255, 255, 255)

image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.ellipse((8, 8, SIZE - 8, SIZE - 8), fill=ORANGE, outline=BLUE, width=18)

# Hand op een aparte laag: vuist met wijs- en middelvinger gestrekt, daarna iets gedraaid.
hand = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
hand_draw = ImageDraw.Draw(hand)
hand_draw.rounded_rectangle((90, 46, 124, 160), radius=17, fill=WHITE, outline=BLUE, width=5)  # wijsvinger
hand_draw.rounded_rectangle((122, 36, 156, 160), radius=17, fill=WHITE, outline=BLUE, width=5)  # middelvinger
hand_draw.rounded_rectangle((78, 132, 178, 214), radius=30, fill=WHITE, outline=BLUE, width=5)  # vuist
hand_draw.line((96, 150, 160, 150), fill=WHITE, width=12)  # vingers lopen door in de vuist
hand_draw.arc((150, 150, 200, 200), start=180, end=270, fill=BLUE, width=5)  # ingevouwen duim
hand = hand.rotate(-14, resample=Image.BICUBIC, center=(128, 140))
image.alpha_composite(hand)

# Gloed bij de vingertoppen: de teleport.
draw = ImageDraw.Draw(image)
for radius, alpha in ((34, 70), (22, 130), (11, 230)):
    draw.ellipse((160 - radius, 46 - radius, 160 + radius, 46 + radius), fill=(255, 245, 200, alpha))

output = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
image.save(output, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(f"Opgeslagen: {output}")
