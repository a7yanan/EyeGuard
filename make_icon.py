# Builds the program icons from hamsa.png (the eye-in-hand design):
#   logo.png     - yellow, used on the settings window and the installer
#   app.ico      - yellow, the program icon
#   tray_on.ico  - the eye only, yellow, tray icon while EyeGuard runs
#   tray_off.ico - the eye only, red, tray icon while EyeGuard is stopped
# The black background becomes transparent. The blue parts are recoloured; the white eye and the pupil stay.
from PIL import Image, ImageChops, ImageDraw

SRC = "hamsa.png"
YELLOW = [(0.0, (150, 95, 0)), (0.5, (250, 190, 20)), (1.0, (255, 250, 170))]
RED = [(0.0, (120, 10, 10)), (0.5, (230, 50, 50)), (1.0, (255, 190, 190))]


def ramp_color(stops, t):
    t = max(0.0, min(1.0, t))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            f = (t - a) / float(b - a)
            return tuple(int(round(ca[i] + (cb[i] - ca[i]) * f)) for i in range(3))
    return stops[-1][1]


def recolor(src, stops):
    img = src.convert("RGBA")
    out = Image.new("RGBA", img.size)
    px = img.load()
    po = out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            m = max(r, g, b)
            alpha = int(max(0.0, min(1.0, (m - 22) / 40.0)) * 255)     # black background -> transparent
            if b > r + 40 and m >= 90:                                  # the blue parts of the hand
                lum = (0.3 * r + 0.59 * g + 0.11 * b) / 255.0
                cr, cg, cb = ramp_color(stops, (lum - 0.25) / 0.6)
                po[x, y] = (cr, cg, cb, alpha)
            else:                                                       # white eye, dark pupil, highlight
                po[x, y] = (r, g, b, alpha)
    return out


def enlarge_eye(img, factor=1.6):
    """Makes the eye in the middle of the hand bigger, so it can be seen in the small tray icon."""
    cx, cy, rx, ry = 256, 322, 116, 78
    box = (cx - rx - 8, cy - ry - 8, cx + rx + 8, cy + ry + 8)
    crop = img.crop(box)
    mask = Image.new("L", (512, 512), 0)
    ImageDraw.Draw(mask).ellipse((cx - rx - 4, cy - ry - 4, cx + rx + 4, cy + ry + 4), fill=255)
    big = crop.resize((int(crop.width * factor), int(crop.height * factor)), Image.LANCZOS)
    big_mask = mask.crop(box).resize(big.size, Image.LANCZOS)
    big.putalpha(ImageChops.multiply(big.getchannel("A"), big_mask))
    layer = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    layer.paste(big, (cx - big.width // 2, cy - big.height // 2), big)
    return Image.alpha_composite(img, layer)


def fit_square(img, margin=0.02):
    """Cuts the empty border away and fills the square, so the icon is as big as the other tray icons."""
    alpha = img.getchannel("A").point(lambda v: 255 if v > 20 else 0)
    box = alpha.getbbox()
    if box is None:
        return img
    crop = img.crop(box)
    side = max(crop.size)
    inner = int(side * (1 - 2 * margin))
    scale = inner / float(side)
    crop = crop.resize((max(1, int(crop.size[0] * scale)), max(1, int(crop.size[1] * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(crop, ((side - crop.size[0]) // 2, (side - crop.size[1]) // 2), crop)
    return out


# a white eye with a yellow iris (the same as the movement screen)
PAL = {"sclera": (255, 255, 255, 255), "edge": (30, 41, 59, 255), "iris": (245, 158, 11, 255),
       "pupil": (17, 24, 39, 255)}


def tray_eye(on):
    """Only the eye, filling the whole tray icon, on a transparent background (same as in the program)."""
    S, ss = 256, 2
    W = S * ss
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = W / 2.0
    p = PAL
    rx, ry = 126 * ss, 70 * ss
    d.ellipse((c - rx, c - ry, c + rx, c + ry), fill=p["sclera"], outline=p["edge"], width=7 * ss)
    ir = 60 * ss
    d.ellipse((c - ir, c - ir, c + ir, c + ir), fill=p["iris"])
    pr = 28 * ss
    d.ellipse((c - pr, c - pr, c + pr, c + pr), fill=p["pupil"])
    d.ellipse((c + 14 * ss, c - 26 * ss, c + 26 * ss, c - 14 * ss), fill=(255, 255, 255, 255))
    return im.resize((S, S), Image.LANCZOS)


def save_ico(img, path):
    img.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    src = Image.open(SRC)
    base = src.convert("RGBA").resize((512, 512), Image.LANCZOS)
    yellow = recolor(base, YELLOW)
    red = recolor(base, RED)
    yellow.save("logo.png")                       # the settings logo keeps its layout (the eye blinks on it)
    yellow_fit = fit_square(yellow).resize((256, 256), Image.LANCZOS)
    red_fit = fit_square(red).resize((256, 256), Image.LANCZOS)
    save_ico(yellow_fit, "app.ico")
    save_ico(tray_eye(True), "tray_on.ico")       # tray icons: the eye only, as big as possible
    save_ico(tray_eye(False), "tray_off.ico")
    print("icons created")
